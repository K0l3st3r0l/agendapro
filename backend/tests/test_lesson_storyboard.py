"""Pruebas de la generación de storyboard, con proveedor falso.

No tocan la red ni la base de datos: reemplazan `providers.generate_json` por
una función que devuelve lo que la prueba decida. Lo que se verifica es el
contrato con el proveedor —prompt, reintento, errores— no el proveedor.

Corre con pytest si está disponible, o directo:
    docker exec agendapro-backend python /app/tests/test_lesson_storyboard.py
"""

import asyncio
import copy
import json
import os
import sys

sys.path.insert(0, "/app")

from fastapi import HTTPException  # noqa: E402

from app.api import lessons  # noqa: E402
from app.api.lessons import StoryboardRequest, _build_prompt, _reglas_de_nivel  # noqa: E402
from app.schemas.lesson import LessonDraft  # noqa: E402
from app.services import providers  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "lesson_oa11_matematica.json")


CAMPOS_DEL_SERVIDOR = ("uri", "source", "status", "credit")


def draft_valido() -> dict:
    """Lo que emitiría el modelo: la fixture menos lo que llena el servidor."""
    with open(FIXTURE, encoding="utf-8") as fh:
        spec = json.load(fh)
    return {
        "metadata": spec["metadata"],
        "scenes": spec["scenes"],
        "questions": spec["questions"],
        "assets": [
            {k: v for k, v in a.items() if k not in CAMPOS_DEL_SERVIDOR} for a in spec["assets"]
        ],
        "teacher_notes": spec["teacher_notes"],
        "exit_assessment": spec["exit_assessment"],
    }


class ProveedorFalso:
    """Devuelve las respuestas que le pasen, en orden, y guarda los prompts."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.prompts = []

    async def __call__(self, settings, *, prompt, system, **kwargs):
        self.prompts.append(prompt)
        contenido = self.respuestas.pop(0)
        if isinstance(contenido, Exception):
            raise contenido
        return providers.GenerationResult(
            content=contenido, text="", provider="falso", model="falso-1", cost=0.001
        )


def con_proveedor(fake, corutina):
    original = providers.generate_json
    providers.generate_json = fake
    try:
        return asyncio.run(corutina())
    finally:
        providers.generate_json = original


def generar(fake, grade_level="1° Básico"):
    async def corre():
        return await lessons._generar_validado(None, "PROMPT", grade_level, None)

    return con_proveedor(fake, corre)


# ---------------------------------------------------------------------------
# Camino feliz y reintento
# ---------------------------------------------------------------------------

def test_json_valido_a_la_primera_no_reintenta():
    fake = ProveedorFalso(draft_valido())
    draft, result = generar(fake)
    assert isinstance(draft, LessonDraft)
    assert len(fake.prompts) == 1
    assert result.provider == "falso"


def test_primer_intento_invalido_y_segundo_valido():
    malo = draft_valido()
    malo["scenes"][3]["data"]["question_ref"] = "no-existe"
    fake = ProveedorFalso(malo, draft_valido())

    draft, result = generar(fake)
    assert len(draft.scenes) == 5
    assert len(fake.prompts) == 2


def test_el_reintento_lleva_los_errores_concretos():
    """Sin el error concreto el modelo repite la misma falla y se gasta la
    segunda llamada para nada."""
    malo = draft_valido()
    malo["scenes"][3]["data"]["question_ref"] = "no-existe"
    fake = ProveedorFalso(malo, draft_valido())
    generar(fake)

    reintento = fake.prompts[1]
    assert "no-existe" in reintento
    assert "no corresponde a ninguna pregunta" in reintento


def test_dos_intentos_invalidos_dan_502_visible():
    malo = draft_valido()
    malo["scenes"] = malo["scenes"][:1]  # sin recap y con muy pocas escenas
    fake = ProveedorFalso(malo, copy.deepcopy(malo))

    try:
        generar(fake)
    except HTTPException as exc:
        assert exc.status_code == 502
        assert "dos veces" in exc.detail
        assert len(fake.prompts) == 2
        return
    raise AssertionError("dos respuestas inválidas deben terminar en 502, no en una clase a medias")


def test_json_cortado_por_max_tokens_tambien_reintenta():
    """El modo de falla más frecuente en la medición real.

    El JSON truncado se lanzaba desde `generate_json`, fuera del alcance del
    reintento, y mataba la request sin segunda oportunidad.
    """
    cortado = providers.InvalidJSONError(
        "OpenRouter se quedó sin espacio a mitad de la respuesta (max_tokens=6000) "
        "y el JSON quedó cortado."
    )
    fake = ProveedorFalso(cortado, draft_valido())

    draft, _ = generar(fake)
    assert len(draft.scenes) == 5
    assert len(fake.prompts) == 2
    assert "quedó cortado" in fake.prompts[1]
    assert "acorta el contenido" in fake.prompts[1]


def test_dos_json_invalidos_seguidos_no_quedan_en_bucle():
    fake = ProveedorFalso(
        providers.InvalidJSONError("no es JSON válido."),
        providers.InvalidJSONError("no es JSON válido."),
    )
    try:
        generar(fake)
    except HTTPException as exc:
        assert exc.status_code == 502
        assert len(fake.prompts) == 2
        return
    raise AssertionError("dos respuestas no parseables deben cortar, no reintentar sin fin")


def test_un_402_sin_creditos_no_se_reintenta():
    """Reintentar un error de cuota solo gasta tiempo: el segundo intento falla igual."""
    fake = ProveedorFalso(HTTPException(status_code=402, detail="sin créditos"))
    try:
        generar(fake)
    except HTTPException as exc:
        assert exc.status_code == 402
        assert len(fake.prompts) == 1
        return
    raise AssertionError("un 402 debe propagarse tal cual, sin segunda llamada")


def test_campo_inventado_por_el_modelo_gatilla_reintento():
    malo = draft_valido()
    malo["scenes"][0]["gsap_timeline"] = "gsap.to('.x', {y: 100})"
    fake = ProveedorFalso(malo, draft_valido())

    generar(fake)
    assert "gsap_timeline" in fake.prompts[1]


def test_el_costo_de_los_dos_intentos_se_suma():
    malo = draft_valido()
    malo["scenes"][4]["data"]["key_points"] = []
    fake = ProveedorFalso(malo, draft_valido())

    _, result = generar(fake)
    assert result.cost == 0.002


def test_los_limites_se_aplican_segun_el_curso():
    """El mismo draft pasa en 5° y falla en 1°: es el nivel el que manda."""
    largo = draft_valido()
    largo["scenes"][0]["body"] = (
        "Un patrón es una secuencia de elementos que se repite siempre en el mismo orden y que podemos continuar."
    )

    generar(ProveedorFalso(copy.deepcopy(largo)), grade_level="5° Básico")

    fake = ProveedorFalso(copy.deepcopy(largo), draft_valido())
    generar(fake, grade_level="1° Básico")
    assert "el máximo para 1° Básico es 90" in fake.prompts[1]


# ---------------------------------------------------------------------------
# Currículum
# ---------------------------------------------------------------------------

class BloqueFalso:
    block = "CURRÍCULUM OFICIAL MINEDUC — OA1, OA2, OA3..."


def test_sin_oa_elegido_el_spec_no_afirma_cubrir_toda_la_asignatura():
    """`fetch_oa` sin filtro devuelve los ~30 OA de la asignatura.

    Volcarlos en `resolved_oas` haría que la clase declarara cubrir treinta
    objetivos de aprendizaje, que es falso y además infla el spec guardado.
    """
    original = lessons.curriculum_context.build_context
    lessons.curriculum_context.build_context = lambda *a, **k: BloqueFalso()
    try:
        curriculum, bloque = lessons._resolver_curriculum(None, _request(oa_refs=[]))
    finally:
        lessons.curriculum_context.build_context = original

    assert curriculum.resolved_oas == []
    assert curriculum.resolved_indicators == []
    assert curriculum.grade_level == "1° Básico"
    # El bloque sí se entrega al modelo para orientarlo, aunque no se persista.
    assert bloque


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def _request(**extra) -> StoryboardRequest:
    base = dict(
        grade_level="1° Básico",
        subject="Matemática",
        topic="Patrones repetitivos",
        duration_minutes=45,
    )
    base.update(extra)
    return StoryboardRequest(**base)


def test_el_prompt_de_1_basico_advierte_sobre_lectores_iniciales():
    reglas = _reglas_de_nivel("1° Básico")
    assert "LECTORES INICIALES" in reglas
    assert "máximo 90 caracteres" in reglas
    assert "asset_id" in reglas


def test_el_prompt_de_5_basico_no_lleva_esa_advertencia():
    reglas = _reglas_de_nivel("5° Básico")
    assert "LECTORES INICIALES" not in reglas
    assert "máximo 140 caracteres" in reglas


def test_el_prompt_incluye_el_bloque_curricular():
    bloque = "CURRÍCULUM OFICIAL MINEDUC — OA11: Reconocer patrones..."
    prompt = _build_prompt(_request(), bloque)
    assert bloque in prompt
    assert "Patrones repetitivos" in prompt


def test_el_prompt_respeta_las_indicaciones_de_la_profesora():
    prompt = _build_prompt(_request(instructions="Usar ejemplos con frutas."), "")
    assert "Usar ejemplos con frutas." in prompt


def test_el_prompt_declara_los_cinco_tipos_de_escena_y_ninguno_mas():
    prompt = _build_prompt(_request(), "")
    for tipo in ("concept", "example", "process", "quiz", "recap"):
        assert f'"{tipo}"' in prompt
    for descartado in ("timeline", "comparison", "diagram"):
        assert f'"{descartado}"' not in prompt


def test_el_system_prompt_prohibe_modismos_argentinos():
    assert "vos" in lessons.SYSTEM_PROMPT
    assert "chilena" in lessons.SYSTEM_PROMPT.lower()


def test_el_system_prompt_separa_pantalla_de_narracion():
    assert "narration" in lessons.SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Presupuesto de tokens
# ---------------------------------------------------------------------------

def test_max_tokens_deja_margen_sobre_una_clase_real():
    """Un truncado por `max_tokens` produce JSON inválido y gasta el reintento,
    que es lo que el presupuesto de tiempo no aguanta."""
    tamano = len(json.dumps(draft_valido(), ensure_ascii=False))
    # ~4 caracteres por token es la regla de bolsillo para español.
    tokens_estimados = tamano / 4
    assert lessons.MAX_TOKENS > tokens_estimados * 2, (
        f"la fixture ocupa ~{tokens_estimados:.0f} tokens y max_tokens es {lessons.MAX_TOKENS}"
    )


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
