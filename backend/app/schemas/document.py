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

from app.schemas._jsonschema import gemini_schema_for, openai_schema_for

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
    purpose: str = Field(
        "",
        description=(
            "Propósito pedagógico de la actividad: qué habilidad ejercita y por qué, en una "
            "frase breve. Solo para type='activity'. Vacío si no aplica."
        ),
    )
    indicator_ref: str = Field(
        "",
        description=(
            "Referencia EXACTA del indicador de evaluación que esta actividad trabaja, formato "
            "'CODIGO:N' (ej. 'OA11:3'), copiada tal cual del bloque de currículum entregado. "
            "Vacío si el OA no trae indicadores o el ítem no evalúa uno en particular."
        ),
    )


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
# La lógica vive en `_jsonschema.py` desde que `lesson.py` necesitó lo mismo.
# Estas dos funciones se mantienen sin argumentos porque son las que usa el
# Constructor en producción.


def gemini_schema() -> dict:
    return gemini_schema_for(DocumentContent)


def openai_schema() -> dict:
    return openai_schema_for(DocumentContent)
