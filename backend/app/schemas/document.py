"""Esquema canónico del documento generado por el Constructor IA.

Restricción de diseño: la Gemini API rechaza `anyOf` dentro de un
`response_schema`. Pydantic genera `anyOf` para cualquier campo `Optional[X]`,
así que aquí NO se usan opcionales: todo campo tiene un valor por defecto
concreto (cadena vacía, lista vacía, 0) y el sentinel se interpreta como
"ausente". Eso mantiene el mismo esquema válido para Gemini, OpenAI y
OpenRouter sin ramificaciones por proveedor.

Por la misma razón `Section` separa `body` (texto suelto) de `items` (lista de
preguntas o actividades) en vez de un único campo `content: str | list`, que
era lo que usaba el formato antiguo.
"""

from typing import List, Literal
from pydantic import BaseModel, Field

SectionType = Literal["header", "text", "questions", "activities", "answers"]
ItemType = Literal["multiple_choice", "true_false", "open", "matching", "activity"]
ImageStyle = Literal["none", "photo", "coloring"]


class ContentItem(BaseModel):
    number: int = Field(0, description="Número secuencial dentro de la sección. 0 = asignar automáticamente.")
    text: str = Field("", description="Enunciado de la pregunta o actividad, SIN el número al inicio.")
    type: ItemType = Field("open", description="Tipo de ítem.")
    options: List[str] = Field(default_factory=list, description="Alternativas. Vacío si no es selección múltiple.")
    answer: str = Field("", description="Respuesta correcta. Vacío si el ítem no lleva pauta.")
    points: int = Field(0, description="Puntaje del ítem. 0 = sin puntaje asignado.")
    image_words: List[str] = Field(
        default_factory=list,
        description=(
            "Palabras cuyas imágenes se mostrarán al alumno. Sustantivos concretos y "
            "visuales, siempre la palabra completa (nunca una sola letra). Deben ser "
            "coherentes con el enunciado: si el texto dice 'mira el dibujo de X', X va aquí."
        ),
    )
    image_style: ImageStyle = Field("none", description="'coloring' si la actividad pide pintar o colorear.")


class Section(BaseModel):
    type: SectionType = Field("text", description="Tipo de sección.")
    title: str = Field("", description="Título de la sección. Vacío si no lleva.")
    body: str = Field("", description="Texto corrido de la sección. Vacío si la sección es una lista de ítems.")
    items: List[ContentItem] = Field(
        default_factory=list,
        description="Preguntas o actividades. Vacío si la sección es solo texto.",
    )


class DocumentMetadata(BaseModel):
    subject: str = ""
    grade: str = ""
    topic: str = ""
    total_points: int = 0
    oa_codes: List[str] = Field(
        default_factory=list,
        description="Códigos OA del currículum MINEDUC efectivamente cubiertos. Solo códigos entregados en el contexto; nunca inventar.",
    )


class DocumentContent(BaseModel):
    title: str
    instructions: str = Field("", description="Instrucciones para el alumno.")
    sections: List[Section] = Field(default_factory=list)
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)


# ---------------------------------------------------------------------------
# Conversión a los formatos de esquema que espera cada proveedor
# ---------------------------------------------------------------------------

_UNSUPPORTED_BY_GEMINI = {"default", "title", "additionalProperties", "$defs", "allOf"}


def _inline_refs(node, defs: dict):
    """Resuelve los `$ref` que Pydantic genera para modelos anidados.

    Gemini no acepta `$ref`/`$defs`, así que cada referencia se reemplaza por
    una copia del modelo apuntado. El esquema no es recursivo, por lo que
    inlinear no puede entrar en bucle.
    """
    if isinstance(node, list):
        return [_inline_refs(n, defs) for n in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        return _inline_refs(defs[name], defs)

    # Pydantic envuelve los modelos anidados con default en allOf: [{$ref}]
    if "allOf" in node and len(node["allOf"]) == 1:
        merged = _inline_refs(node["allOf"][0], defs)
        return merged

    return {k: _inline_refs(v, defs) for k, v in node.items()}


def _walk(node, transform):
    """Recorre un JSON Schema aplicando `transform` a cada nodo de esquema.

    Distingue las claves de `properties` —que son nombres de campo elegidos por
    nosotros, como `title`— de las palabras clave de JSON Schema. Sin esa
    distinción, filtrar la keyword `title` borraba también la propiedad
    `title` del documento.
    """
    if isinstance(node, list):
        return [_walk(n, transform) for n in node]
    if not isinstance(node, dict):
        return node

    out = {}
    for key, value in node.items():
        if key == "properties" and isinstance(value, dict):
            out[key] = {name: _walk(sub, transform) for name, sub in value.items()}
        else:
            out[key] = _walk(value, transform)
    return transform(out)


def _inlined_root() -> dict:
    raw = DocumentContent.model_json_schema()
    defs = raw.get("$defs", {})
    return _inline_refs({k: v for k, v in raw.items() if k != "$defs"}, defs)


def gemini_schema() -> dict:
    """Esquema sin `$ref`, `default` ni `additionalProperties`."""

    def prune(node: dict) -> dict:
        return {k: v for k, v in node.items() if k not in _UNSUPPORTED_BY_GEMINI}

    return _walk(_inlined_root(), prune)


def openai_schema() -> dict:
    """Esquema para `response_format={"type":"json_schema", strict: true}`.

    El modo estricto exige `additionalProperties: false` y que `required`
    liste *todas* las propiedades de cada objeto.
    """

    def strictify(node: dict) -> dict:
        out = {k: v for k, v in node.items() if k not in {"default", "$defs"}}
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"].keys())
        return out

    return _walk(_inlined_root(), strictify)
