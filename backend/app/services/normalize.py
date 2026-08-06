"""Normalización de documentos al esquema canónico.

Cubre dos entradas distintas:

1. **Documentos legacy** guardados antes del esquema validado, donde
   `section.content` podía ser un string, una lista de strings o una lista de
   dicts con nombres de campo variables (`text` / `question` / `activity`).
   El documento id=1 en producción es del primer tipo: un bloque de markdown
   con "1. Imagen de una **abeja**: ..." incrustado y sin `image_words`.

2. **Respuestas del modelo** que ya vienen con el esquema nuevo pero necesitan
   los arreglos determinísticos que no conviene delegarle a la IA: numeración,
   limpieza del número dentro del texto y detección del estilo de imagen.

No se intenta reconstruir `image_words` a partir del texto de un documento
legacy. Eso era un parche para el esquema roto; con `response_schema` forzado
el modelo ya no puede devolver ese formato, así que el parche sobra.
"""

import re
from typing import Any

from app.schemas.document import ContentItem, DocumentContent, DocumentMetadata, Section

_SECTION_TYPES = {"header", "text", "questions", "activities", "answers"}
_ITEM_TYPES = {"multiple_choice", "true_false", "open", "matching", "activity"}
_IMAGE_STYLES = {"none", "photo", "coloring"}

_LEADING_NUMBER = re.compile(r"^\s*\d+\s*[\.\)\-]\s*")
_COLORING_HINTS = ("pinta", "colorea", "colorear", "pintar")


def _item_text(raw: dict) -> str:
    for key in ("text", "question", "activity", "description", "content", "title"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _coerce_item(raw: Any) -> ContentItem:
    if isinstance(raw, str):
        return ContentItem(text=_LEADING_NUMBER.sub("", raw).strip())
    if not isinstance(raw, dict):
        return ContentItem(text=str(raw))

    text = _LEADING_NUMBER.sub("", _item_text(raw)).strip()

    options = [str(o) for o in raw.get("options") or [] if str(o).strip()]
    # Nunca una sola letra: "P" no se puede ilustrar, la palabra completa sí.
    words = [str(w).strip().lower() for w in raw.get("image_words") or []]
    words = [w for w in words if len(w) > 1]

    style = raw.get("image_style") if raw.get("image_style") in _IMAGE_STYLES else "none"
    if style == "none" and words:
        lowered = text.lower()
        style = "coloring" if any(h in lowered for h in _COLORING_HINTS) else "photo"

    item_type = raw.get("type") if raw.get("type") in _ITEM_TYPES else None
    if item_type is None:
        item_type = "multiple_choice" if options else "open"

    def _as_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    return ContentItem(
        number=_as_int(raw.get("number")),
        text=text,
        type=item_type,
        options=options,
        answer=str(raw.get("answer") or "").strip(),
        points=_as_int(raw.get("points")),
        image_words=words,
        image_style=style,
    )


def _coerce_section(raw: Any) -> Section:
    if not isinstance(raw, dict):
        return Section(body=str(raw))

    sec_type = raw.get("type") if raw.get("type") in _SECTION_TYPES else "text"
    title = str(raw.get("title") or "").strip()

    # Formato nuevo: body + items ya separados.
    if "items" in raw or "body" in raw:
        items = [_coerce_item(i) for i in raw.get("items") or []]
        body = str(raw.get("body") or "").strip()
    else:
        # Formato legacy: un único `content` polimórfico.
        content = raw.get("content")
        if isinstance(content, list):
            items = [_coerce_item(i) for i in content]
            body = ""
        else:
            items = []
            body = str(content or "").strip()

    # Numeración por sección, no global: antes un contador compartido entre
    # secciones dejaba la pauta de respuestas numerada 11-20 en vez de 1-10.
    # Solo se reasigna si el modelo no entregó una secuencia ya correcta.
    expected = list(range(1, len(items) + 1))
    if [i.number for i in items] != expected:
        for position, item in enumerate(items, start=1):
            item.number = position

    return Section(type=sec_type, title=title, body=body, items=items)


def _coerce_metadata(raw: Any) -> DocumentMetadata:
    if not isinstance(raw, dict):
        return DocumentMetadata()
    try:
        total = int(raw.get("total_points") or 0)
    except (TypeError, ValueError):
        total = 0
    return DocumentMetadata(
        subject=str(raw.get("subject") or ""),
        grade=str(raw.get("grade") or raw.get("grade_level") or ""),
        topic=str(raw.get("topic") or ""),
        total_points=total,
        oa_codes=[str(c).strip() for c in raw.get("oa_codes") or [] if str(c).strip()],
    )


def normalize_document(raw: Any) -> DocumentContent:
    """Convierte cualquier forma conocida de documento al esquema canónico."""
    if isinstance(raw, DocumentContent):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("El documento debe ser un objeto JSON")

    sections_raw = raw.get("sections")
    sections = [_coerce_section(s) for s in sections_raw] if isinstance(sections_raw, list) else []

    return DocumentContent(
        title=str(raw.get("title") or "Documento").strip(),
        instructions=str(raw.get("instructions") or "").strip(),
        sections=sections,
        metadata=_coerce_metadata(raw.get("metadata")),
    )


def collect_image_words(doc: DocumentContent) -> dict[str, str]:
    """Mapea cada palabra ilustrable a su estilo, deduplicando entre secciones."""
    mapping: dict[str, str] = {}
    for section in doc.sections:
        for item in section.items:
            style = item.image_style if item.image_style in ("photo", "coloring") else "photo"
            for word in item.image_words:
                mapping.setdefault(word, style)
    return mapping
