"""Pruebas del normalizador de documentos.

Corre con pytest si está disponible, o directo:
    docker exec agendapro-backend python /app/tests/test_normalize.py
"""

import sys

sys.path.insert(0, "/app")

from app.schemas.document import gemini_schema, openai_schema  # noqa: E402
from app.services.normalize import collect_image_words, normalize_document  # noqa: E402


def test_legacy_content_string_va_a_body():
    doc = normalize_document(
        {"title": "T", "sections": [{"type": "text", "title": "S", "content": "texto suelto"}]}
    )
    assert doc.sections[0].body == "texto suelto"
    assert doc.sections[0].items == []


def test_legacy_lista_de_strings_va_a_items():
    doc = normalize_document({"title": "T", "sections": [{"content": ["uno", "dos"]}]})
    items = doc.sections[0].items
    assert [i.text for i in items] == ["uno", "dos"]
    assert [i.number for i in items] == [1, 2]


def test_nombres_de_campo_alternativos():
    """El modelo a veces devuelve `question` o `activity` en vez de `text`."""
    doc = normalize_document(
        {"title": "T", "sections": [{"content": [{"question": "¿Cuánto es 2+2?"}, {"activity": "Dibuja"}]}]}
    )
    assert [i.text for i in doc.sections[0].items] == ["¿Cuánto es 2+2?", "Dibuja"]


def test_numero_dentro_del_texto_se_quita():
    doc = normalize_document({"title": "T", "sections": [{"content": [{"text": "1. Actividad uno"}]}]})
    item = doc.sections[0].items[0]
    assert item.text == "Actividad uno"
    assert item.number == 1


def test_numeracion_es_por_seccion_no_global():
    """El bug: con 10 preguntas + 10 respuestas, la pauta salía numerada 11-20."""
    doc = normalize_document(
        {
            "title": "Prueba",
            "sections": [
                {"type": "questions", "content": [{"text": f"P{n}"} for n in range(1, 11)]},
                {"type": "answers", "content": [{"text": f"R{n}"} for n in range(1, 11)]},
            ],
        }
    )
    assert [i.number for i in doc.sections[0].items] == list(range(1, 11))
    assert [i.number for i in doc.sections[1].items] == list(range(1, 11)), "la pauta debe partir en 1"


def test_numeracion_correcta_del_modelo_se_respeta():
    doc = normalize_document(
        {"title": "T", "sections": [{"content": [{"number": 1, "text": "a"}, {"number": 2, "text": "b"}]}]}
    )
    assert [i.number for i in doc.sections[0].items] == [1, 2]


def test_image_words_de_una_letra_se_descartan():
    doc = normalize_document(
        {"title": "T", "sections": [{"content": [{"text": "x", "image_words": ["P", "abeja", "M", "sol"]}]}]}
    )
    assert doc.sections[0].items[0].image_words == ["abeja", "sol"]


def test_estilo_coloring_se_detecta_del_texto():
    doc = normalize_document(
        {"title": "T", "sections": [{"content": [{"text": "Pinta la abeja", "image_words": ["abeja"]}]}]}
    )
    assert doc.sections[0].items[0].image_style == "coloring"


def test_estilo_photo_por_defecto_cuando_hay_palabras():
    doc = normalize_document(
        {"title": "T", "sections": [{"content": [{"text": "Une cada imagen", "image_words": ["pato"]}]}]}
    )
    assert doc.sections[0].items[0].image_style == "photo"


def test_formato_nuevo_body_items_pasa_intacto():
    doc = normalize_document(
        {
            "title": "T",
            "sections": [{"type": "activities", "body": "intro", "items": [{"text": "act", "number": 1}]}],
        }
    )
    assert doc.sections[0].body == "intro"
    assert doc.sections[0].items[0].text == "act"


def test_collect_image_words_deduplica_entre_secciones():
    doc = normalize_document(
        {
            "title": "T",
            "sections": [
                {"content": [{"text": "Une", "image_words": ["sol", "luna"]}]},
                {"content": [{"text": "Pinta", "image_words": ["sol"], "image_style": "coloring"}]},
            ],
        }
    )
    mapping = collect_image_words(doc)
    assert mapping == {"sol": "photo", "luna": "photo"}, "la primera aparición fija el estilo"


def test_purpose_e_indicator_ref_pasan_intactos():
    doc = normalize_document(
        {
            "title": "Guía",
            "sections": [
                {
                    "type": "activities",
                    "items": [{"text": "Cuenta hasta 10", "purpose": "Ejercitar el conteo", "indicator_ref": "OA1:2"}],
                }
            ],
        }
    )
    item = doc.sections[0].items[0]
    assert item.purpose == "Ejercitar el conteo"
    assert item.indicator_ref == "OA1:2"


def test_purpose_e_indicator_ref_ausentes_quedan_vacios():
    doc = normalize_document({"title": "T", "sections": [{"content": [{"text": "a"}]}]})
    item = doc.sections[0].items[0]
    assert item.purpose == ""
    assert item.indicator_ref == ""


def test_documento_sin_secciones_no_revienta():
    doc = normalize_document({"title": "Vacío"})
    assert doc.sections == []
    assert doc.metadata.total_points == 0


def test_puntaje_no_numerico_no_revienta():
    doc = normalize_document({"title": "T", "sections": [{"content": [{"text": "a", "points": "dos"}]}]})
    assert doc.sections[0].items[0].points == 0


def test_esquema_gemini_sin_construcciones_no_soportadas():
    import json

    raw = json.dumps(gemini_schema())
    for prohibido in ("anyOf", "$ref", "$defs", "allOf", "additionalProperties"):
        assert prohibido not in raw, f"Gemini rechaza {prohibido} en response_schema"
    assert "title" in gemini_schema()["properties"], "la propiedad title no debe perderse al filtrar"


def test_esquema_openai_es_estricto():
    schema = openai_schema()
    assert schema["additionalProperties"] is False
    assert schema["required"] == list(schema["properties"].keys())


if __name__ == "__main__":
    fallos = 0
    pruebas = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for nombre, fn in pruebas:
        try:
            fn()
            print(f"  ok    {nombre}")
        except AssertionError as e:
            fallos += 1
            print(f"  FALLA {nombre}: {e}")
        except Exception as e:
            fallos += 1
            print(f"  ERROR {nombre}: {type(e).__name__}: {e}")
    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas OK")
    sys.exit(1 if fallos else 0)
