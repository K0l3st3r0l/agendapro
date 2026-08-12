"""Conversión de modelos Pydantic a los formatos de esquema de cada proveedor.

Extraído de `document.py`, donde estos helpers ya resolvían el problema real:
la Gemini API rechaza `$ref`, `$defs`, `anyOf`, `default` y
`additionalProperties` dentro de un `response_schema`, y el modo estricto de
OpenAI exige justo lo contrario (`additionalProperties: false` y un `required`
que liste *todas* las propiedades).

Aquí no hay nada específico de documentos: recibe el modelo por parámetro para
que `document.py` y `lesson.py` compartan la misma solución en vez de tener dos
copias que se desincronizan.
"""

from typing import Type

from pydantic import BaseModel

# Claves de JSON Schema que Gemini rechaza en un response_schema.
UNSUPPORTED_BY_GEMINI = {"default", "title", "additionalProperties", "$defs", "allOf"}


def _inline_refs(node, defs: dict):
    """Resuelve los `$ref` que Pydantic genera para modelos anidados.

    Gemini no acepta `$ref`/`$defs`, así que cada referencia se reemplaza por
    una copia del modelo apuntado. Los esquemas no son recursivos, por lo que
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
        return _inline_refs(node["allOf"][0], defs)

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


def _strip_model_docstrings(node):
    """Quita la `description` que Pydantic hereda del docstring de cada modelo.

    Esos docstrings explican decisiones de diseño a quien lee el código, y no
    tienen ningún destinatario en el proveedor: viajaban en cada request
    gastando tokens de entrada contra el presupuesto de latencia. Las
    descripciones de los *campos* sí se conservan, porque esas sí son
    instrucciones para el modelo.

    Se distinguen por posición: el docstring de la clase queda como
    `description` de un nodo `type: object` con `properties`; la de un campo
    queda en la propiedad misma.
    """
    if isinstance(node, list):
        return [_strip_model_docstrings(n) for n in node]
    if not isinstance(node, dict):
        return node

    out = {k: _strip_model_docstrings(v) for k, v in node.items()}
    if out.get("type") == "object" and "properties" in out:
        out.pop("description", None)
    return out


def inlined_root(model: Type[BaseModel]) -> dict:
    raw = model.model_json_schema()
    defs = raw.get("$defs", {})
    inlined = _inline_refs({k: v for k, v in raw.items() if k != "$defs"}, defs)
    return _strip_model_docstrings(inlined)


def gemini_schema_for(model: Type[BaseModel]) -> dict:
    """Esquema sin `$ref`, `default` ni `additionalProperties`."""

    def prune(node: dict) -> dict:
        return {k: v for k, v in node.items() if k not in UNSUPPORTED_BY_GEMINI}

    return _walk(inlined_root(model), prune)


def openai_schema_for(model: Type[BaseModel]) -> dict:
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

    return _walk(inlined_root(model), strictify)
