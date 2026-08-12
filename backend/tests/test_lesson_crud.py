"""Pruebas del CRUD de clases contra la API real y PostgreSQL.

No usa una base falsa: el modelo guarda el spec en `JSONB`, que es específico de
PostgreSQL, así que probarlo en SQLite verificaría otra cosa. Crea sus propias
filas y las borra al terminar; no toca datos existentes.

Requiere el backend arriba. Corre con:
    docker exec agendapro-backend python /app/tests/test_lesson_crud.py
"""

import json
import os
import sys

sys.path.insert(0, "/app")

import httpx  # noqa: E402

from app.utils.auth import create_access_token  # noqa: E402

BASE = "http://localhost:8000/api/lessons"
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "lesson_oa11_matematica.json")

TOKEN_DUENA = create_access_token({"sub": "1"})
TOKEN_OTRA = create_access_token({"sub": "2"})
H = {"Authorization": f"Bearer {TOKEN_DUENA}"}
H_OTRA = {"Authorization": f"Bearer {TOKEN_OTRA}"}

creadas = []


def spec_fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def crear(status="draft") -> int:
    r = httpx.post(BASE, json={"spec": spec_fixture(), "status": status}, headers=H, timeout=30)
    assert r.status_code == 200, r.text
    lesson_id = r.json()["id"]
    creadas.append(lesson_id)
    return lesson_id


# ---------------------------------------------------------------------------

def test_crear_y_obtener():
    lesson_id = crear()
    r = httpx.get(f"{BASE}/{lesson_id}", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "Los patrones se repiten"
    assert d["subject"] == "Matemática"
    assert d["grade_level"] == "1° Básico"
    assert len(d["spec"]["scenes"]) == 5


def test_el_listado_no_trae_el_spec_completo():
    """La biblioteca muestra decenas de clases; mandar cada spec entero sería
    varios cientos de KB para pintar una lista de títulos."""
    crear()
    r = httpx.get(BASE, headers=H, timeout=30)
    assert r.status_code == 200
    fila = r.json()["lessons"][0]
    assert "spec" not in fila
    assert fila["scenes"] == 5


def test_present_no_devuelve_las_notas_del_docente():
    """Se filtran en el backend: si viajaran al navegador bastaría abrir la
    consola delante del curso para leerlas."""
    lesson_id = crear()

    completo = httpx.get(f"{BASE}/{lesson_id}", headers=H, timeout=30).json()
    assert completo["spec"]["teacher_notes"]["before_class"]
    assert any(e["teacher_note"] for e in completo["spec"]["scenes"])

    publico = httpx.get(f"{BASE}/{lesson_id}/present", headers=H, timeout=30).json()
    assert publico["spec"]["teacher_notes"]["before_class"] == ""
    assert all(not e["teacher_note"] for e in publico["spec"]["scenes"])
    # Lo que sí va al proyector se conserva.
    assert publico["spec"]["scenes"][0]["body"]
    assert publico["spec"]["questions"][0]["correct_option_ids"]


def test_actualizar_cambia_el_spec_y_el_titulo():
    lesson_id = crear()
    spec = spec_fixture()
    spec["metadata"]["title"] = "Título corregido"
    spec["scenes"][0]["body"] = "Texto corregido."

    r = httpx.put(f"{BASE}/{lesson_id}", json={"spec": spec, "status": "ready"}, headers=H, timeout=30)
    assert r.status_code == 200

    d = httpx.get(f"{BASE}/{lesson_id}", headers=H, timeout=30).json()
    assert d["title"] == "Título corregido"
    assert d["status"] == "ready"
    assert d["spec"]["scenes"][0]["body"] == "Texto corregido."


def test_un_spec_invalido_se_rechaza_al_guardar():
    """El contrato se valida también al persistir, no solo al generar: el editor
    manda el spec que la profesora tocó a mano."""
    spec = spec_fixture()
    spec["scenes"][0]["type"] = "timeline"
    r = httpx.post(BASE, json={"spec": spec}, headers=H, timeout=30)
    assert r.status_code == 422


def test_borrar():
    lesson_id = crear()
    assert httpx.delete(f"{BASE}/{lesson_id}", headers=H, timeout=30).status_code == 200
    assert httpx.get(f"{BASE}/{lesson_id}", headers=H, timeout=30).status_code == 404
    creadas.remove(lesson_id)


# ---------------------------------------------------------------------------
# Aislamiento entre usuarias
# ---------------------------------------------------------------------------

def test_una_clase_ajena_da_404_y_no_403():
    """403 confirmaría que la clase existe, que es justo lo que no corresponde
    revelar a quien no es su autora."""
    lesson_id = crear()
    for metodo, kwargs in [
        (httpx.get, {}),
        (httpx.put, {"json": {"spec": spec_fixture()}}),
        (httpx.delete, {}),
    ]:
        r = metodo(f"{BASE}/{lesson_id}", headers=H_OTRA, timeout=30, **kwargs)
        assert r.status_code == 404, f"{metodo.__name__} devolvió {r.status_code}"


def test_present_de_una_clase_ajena_tambien_da_404():
    lesson_id = crear()
    r = httpx.get(f"{BASE}/{lesson_id}/present", headers=H_OTRA, timeout=30)
    assert r.status_code == 404


def test_el_listado_solo_muestra_las_propias():
    lesson_id = crear()
    ajenas = httpx.get(BASE, headers=H_OTRA, timeout=30).json()["lessons"]
    assert lesson_id not in [c["id"] for c in ajenas]


def test_sin_token_no_se_entra():
    assert httpx.get(BASE, timeout=30).status_code == 403


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

    for lesson_id in creadas:
        httpx.delete(f"{BASE}/{lesson_id}", headers=H, timeout=30)
    print(f"  (limpieza: {len(creadas)} clases de prueba eliminadas)")

    print(f"\n{len(pruebas) - fallos}/{len(pruebas)} pruebas OK")
    sys.exit(1 if fallos else 0)
