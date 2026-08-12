"""Pruebas del contrato LessonSpec v1.

Corre con pytest si está disponible, o directo:
    docker exec agendapro-backend python /app/tests/test_lesson_schema.py
"""

import copy
import json
import os
import sys

sys.path.insert(0, "/app")

from pydantic import ValidationError  # noqa: E402

from app.schemas.lesson import (  # noqa: E402
    Curriculum,
    LessonDraft,
    LessonSpec,
    Option,
    Scene,
    build_spec,
    gemini_schema,
    nivel_de,
    normalizar_query,
    openai_schema,
    public_spec,
    validate_semantics,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "lesson_oa11_matematica.json")


def cargar_spec() -> dict:
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


CAMPOS_DEL_SERVIDOR = ("uri", "source", "status", "credit")


def cargar_draft() -> LessonDraft:
    """El draft es el subconjunto que genera la IA.

    La fixture es un spec completo, con los assets ya resueltos; para volver a
    lo que emitiría el modelo hay que quitarle lo que pone el servidor.
    """
    spec = cargar_spec()
    return LessonDraft(
        metadata=spec["metadata"],
        scenes=spec["scenes"],
        questions=spec["questions"],
        assets=[
            {k: v for k, v in a.items() if k not in CAMPOS_DEL_SERVIDOR} for a in spec["assets"]
        ],
        teacher_notes=spec["teacher_notes"],
        exit_assessment=spec["exit_assessment"],
    )


def _falla(draft: LessonDraft, grade: str = "1° Básico") -> str:
    """Devuelve el mensaje de error de validate_semantics, o falla la prueba."""
    try:
        validate_semantics(draft, grade)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("se esperaba un ValueError y no hubo ninguno")


# ---------------------------------------------------------------------------
# Fixture y camino feliz
# ---------------------------------------------------------------------------

def test_fixture_es_un_spec_valido():
    spec = LessonSpec(**cargar_spec())
    assert spec.schema_version == "1.0"
    assert len(spec.scenes) == 5
    assert spec.curriculum.resolved_oas[0].oa_id == 19


def test_fixture_pasa_la_validacion_semantica_de_1_basico():
    validate_semantics(cargar_draft(), "1° Básico")


def test_fixture_tambien_pasa_en_un_nivel_mas_permisivo():
    validate_semantics(cargar_draft(), "5° Básico")


# ---------------------------------------------------------------------------
# Reglas estructurales del schema
# ---------------------------------------------------------------------------

def test_campo_desconocido_se_rechaza():
    spec = cargar_spec()
    spec["scenes"][0]["animacion_custom"] = "gsap.to('.x')"
    try:
        LessonSpec(**spec)
    except ValidationError as exc:
        assert "animacion_custom" in str(exc)
        return
    raise AssertionError("extra='forbid' debería rechazar un campo inventado")


def test_tipo_de_escena_invalido_se_rechaza():
    try:
        Scene(id="s1", type="timeline")
    except ValidationError:
        return
    raise AssertionError("'timeline' no es un tipo de escena de la v1")


def test_duracion_fuera_de_rango_se_rechaza():
    try:
        Scene(id="s1", type="concept", duration_seconds=5)
    except ValidationError:
        return
    raise AssertionError("una escena de 5 segundos no debería validar")


def test_el_modelo_no_puede_mandar_uri_de_imagen():
    """`uri` no existe en lo que genera la IA.

    Con `extra="forbid"` el intento se rechaza en vez de ignorarse: una URL que
    no pasó por el pipeline de imágenes no debe llegar nunca al player.
    """
    try:
        LessonDraft(assets=[{"id": "a1", "alt": "x", "uri": "https://ejemplo.cl/x.png"}])
    except ValidationError as exc:
        assert "uri" in str(exc)
        return
    raise AssertionError("el draft no debería aceptar una uri del modelo")


def test_el_servidor_completa_los_campos_de_asset_al_armar_el_spec():
    spec = LessonSpec(**cargar_spec())
    assert spec.assets[0].status == "pending"
    assert spec.assets[0].uri == ""


# ---------------------------------------------------------------------------
# Reglas semánticas por tipo de escena
# ---------------------------------------------------------------------------

def test_quiz_sin_question_ref_falla():
    draft = cargar_draft()
    draft.scenes[3].data.question_ref = ""
    assert "question_ref" in _falla(draft)


def test_quiz_con_question_ref_roto_falla():
    draft = cargar_draft()
    draft.scenes[3].data.question_ref = "q-inexistente"
    assert "no corresponde a ninguna pregunta" in _falla(draft)


def test_process_con_un_solo_paso_falla():
    draft = cargar_draft()
    draft.scenes[2].data.steps = draft.scenes[2].data.steps[:1]
    assert "pasos en data.steps" in _falla(draft)


def test_recap_sin_key_points_falla():
    draft = cargar_draft()
    draft.scenes[4].data.key_points = []
    assert "key_points" in _falla(draft)


def test_clase_sin_recap_falla():
    draft = cargar_draft()
    draft.scenes = draft.scenes[:4]
    assert "recap" in _falla(draft)


def test_ids_de_escena_duplicados_fallan():
    draft = cargar_draft()
    draft.scenes[1].id = draft.scenes[0].id
    assert "IDs de escena repetidos" in _falla(draft)


def test_asset_referenciado_pero_inexistente_falla():
    draft = cargar_draft()
    draft.scenes[0].asset_ids = ["a-fantasma"]
    assert "a-fantasma" in _falla(draft)


def test_asset_sin_alt_falla():
    draft = cargar_draft()
    draft.assets[0].alt = ""
    assert "no tiene alt" in _falla(draft)


def test_respuesta_correcta_que_no_es_alternativa_falla():
    draft = cargar_draft()
    draft.questions[0].correct_option_ids = ["o-inventada"]
    assert "no es una de sus alternativas" in _falla(draft)


def test_pregunta_sin_respuesta_correcta_falla():
    draft = cargar_draft()
    draft.questions[0].correct_option_ids = []
    assert "no declara respuesta correcta" in _falla(draft)


def test_query_larga_se_normaliza_en_vez_de_rechazar_la_clase():
    """Era la causa de 2 de cada 3 rechazos, sin que la clase tuviera nada malo.

    Pagar otra generación completa por una búsqueda de imagen mal escrita es
    desproporcionado: el servidor la arregla y sigue.
    """
    assert normalizar_query("pasos para hacer un patrón repetitivo") == "pasos patrón repetitivo"
    assert normalizar_query("ciclo de vida de una planta") == "ciclo vida planta"
    assert normalizar_query("collar de cuentas") == "collar cuentas"
    assert normalizar_query("manzana") == "manzana"


def test_query_solo_de_palabras_vacias_no_queda_en_blanco():
    assert normalizar_query("de la una") != ""


def test_una_query_larga_ya_no_invalida_el_draft():
    draft = cargar_draft()
    draft.assets[0].query = "pasos para hacer un patrón repetitivo"
    validate_semantics(draft, "1° Básico")


def test_exit_assessment_habilitado_y_vacio_falla():
    """Sin ticket de salida la clase se queda sin evidencia de aprendizaje."""
    draft = cargar_draft()
    draft.exit_assessment.prompt = ""
    assert "no trae prompt" in _falla(draft)


def test_exit_assessment_deshabilitado_puede_ir_vacio():
    draft = cargar_draft()
    draft.exit_assessment.enabled = False
    draft.exit_assessment.prompt = ""
    validate_semantics(draft, "1° Básico")


# ---------------------------------------------------------------------------
# Límites por nivel — el diseño protegido desde el contrato
# ---------------------------------------------------------------------------

def test_nivel_de_reconoce_1_y_2_basico():
    assert nivel_de("1° Básico") == "inicial"
    assert nivel_de("2° Básico") == "inicial"
    assert nivel_de("3° Básico") == "estandar"
    assert nivel_de("8° Básico") == "estandar"


def test_nivel_de_ante_un_string_raro_elige_lo_permisivo():
    assert nivel_de("") == "estandar"
    assert nivel_de("Kinder") == "estandar"


def test_body_largo_falla_en_1_basico_pero_pasa_en_5():
    draft = cargar_draft()
    draft.scenes[0].body = (
        "Un patrón es una secuencia de elementos que se repite siempre en el mismo orden y que podemos continuar."
    )
    assert 90 < len(draft.scenes[0].body) <= 140
    assert "el máximo para 1° Básico es 90" in _falla(draft, "1° Básico")
    validate_semantics(draft, "5° Básico")


def test_key_points_de_mas_se_recortan_en_vez_de_rechazar():
    """Medido: rechazos por "4 puntos en vez de 3" eran la mitad de los
    reintentos, y cada reintento duplica latencia y costo sin que el contenido
    tuviera nada malo."""
    draft = cargar_draft()
    draft.scenes[4].data.key_points = ["Uno.", "Dos.", "Tres.", "Cuatro."]
    validate_semantics(draft, "1° Básico")

    spec = build_spec(draft, curriculum=Curriculum(grade_level="1° Básico"),
                      duration_minutes=45, audience="1° Básico")
    assert spec.scenes[4].data.key_points == ["Uno.", "Dos.", "Tres."]


def test_un_key_point_demasiado_largo_si_falla():
    """Recortar el texto de un punto lo dejaría sin sentido; ahí no se normaliza."""
    draft = cargar_draft()
    draft.scenes[4].data.key_points = ["x" * 95]
    assert "supera los 80 caracteres" in _falla(draft)


def test_ejemplos_de_mas_se_recortan():
    draft = cargar_draft()
    draft.scenes[1].data.examples = draft.scenes[1].data.examples * 2
    validate_semantics(draft, "1° Básico")
    spec = build_spec(draft, curriculum=Curriculum(grade_level="1° Básico"),
                      duration_minutes=45, audience="1° Básico")
    assert len(spec.scenes[1].data.examples) == 2


def test_los_pasos_de_un_proceso_nunca_se_recortan():
    """Truncar un procedimiento lo deja incompleto: la escena dejaría de
    enseñar lo que dice enseñar."""
    draft = cargar_draft()
    cuarto = draft.scenes[2].data.steps[0].model_copy()
    cuarto.id = "p-4"
    draft.scenes[2].data.steps = draft.scenes[2].data.steps + [cuarto]
    validate_semantics(draft, "1° Básico")
    spec = build_spec(draft, curriculum=Curriculum(grade_level="1° Básico"),
                      duration_minutes=45, audience="1° Básico")
    assert len(spec.scenes[2].data.steps) == 4


def test_build_spec_no_muta_el_draft_al_recortar():
    draft = cargar_draft()
    draft.scenes[4].data.key_points = ["Uno.", "Dos.", "Tres.", "Cuatro."]
    build_spec(draft, curriculum=Curriculum(grade_level="1° Básico"),
               duration_minutes=45, audience="1° Básico")
    assert len(draft.scenes[4].data.key_points) == 4


def test_cuatro_alternativas_fallan_en_1_basico():
    draft = cargar_draft()
    draft.questions[0].options.append(Option(id="o-x", label="Amarillo"))
    assert "entre 2 y 3 alternativas" in _falla(draft)


def test_los_errores_se_reportan_todos_juntos():
    """El mensaje va como feedback del reintento: de a un error por vuelta
    gastaría llamadas de más contra el presupuesto de tiempo."""
    draft = cargar_draft()
    draft.scenes[0].body = "x" * 200
    draft.scenes[3].data.question_ref = ""
    draft.questions[0].correct_option_ids = []
    mensaje = _falla(draft)
    assert mensaje.count("\n") >= 2


# ---------------------------------------------------------------------------
# Privacidad
# ---------------------------------------------------------------------------

def test_public_spec_no_lleva_notas_del_docente():
    spec = LessonSpec(**cargar_spec())
    assert spec.teacher_notes.before_class
    assert any(s.teacher_note for s in spec.scenes)

    publico = public_spec(spec)
    assert publico["teacher_notes"]["before_class"] == ""
    assert all(not s["teacher_note"] for s in publico["scenes"])


def test_public_spec_conserva_lo_que_si_va_al_proyector():
    publico = public_spec(LessonSpec(**cargar_spec()))
    assert publico["scenes"][0]["body"] == "Un patrón es un orden que se repite."
    assert publico["questions"][0]["correct_option_ids"] == ["o-azul"]


def test_public_spec_no_muta_el_original():
    spec = LessonSpec(**cargar_spec())
    antes = copy.deepcopy(spec.model_dump())
    public_spec(spec)
    assert spec.model_dump() == antes


# ---------------------------------------------------------------------------
# Compatibilidad con los proveedores
# ---------------------------------------------------------------------------

def _claves_de_esquema(node, encontradas=None):
    """Recolecta las *claves* del JSON Schema.

    Buscar substrings en el dump serializado —como hacía la prueba equivalente
    de `document.py`— da falsos positivos: el docstring de `SceneData` menciona
    `anyOf` justamente para explicar por qué no se usa.
    """
    encontradas = encontradas if encontradas is not None else set()
    if isinstance(node, list):
        for item in node:
            _claves_de_esquema(item, encontradas)
    elif isinstance(node, dict):
        for clave, valor in node.items():
            if clave == "properties" and isinstance(valor, dict):
                for sub in valor.values():
                    _claves_de_esquema(sub, encontradas)
                continue
            encontradas.add(clave)
            _claves_de_esquema(valor, encontradas)
    return encontradas


def test_esquema_gemini_sin_construcciones_no_soportadas():
    claves = _claves_de_esquema(gemini_schema())
    for prohibido in ("$ref", "$defs", "anyOf", "allOf", "additionalProperties", "default"):
        assert prohibido not in claves, f"Gemini rechaza {prohibido} en response_schema"


def test_los_docstrings_de_los_modelos_no_viajan_al_proveedor():
    """Explican decisiones de diseño a quien lee el código; el modelo no los
    necesita y ocupan tokens de entrada en cada llamada."""
    raw = json.dumps(gemini_schema())
    assert "validate_semantics" not in raw
    assert "presupuesto de 25 s" not in raw
    # Las descripciones de campo sí tienen que seguir ahí: son instrucciones.
    assert "Sustantivo concreto y visual" in raw


def test_esquema_gemini_conserva_las_propiedades_del_contrato():
    props = gemini_schema()["properties"]
    assert "scenes" in props and "questions" in props
    # `title` es a la vez keyword de JSON Schema y campo nuestro: el filtro no
    # debe borrar la propiedad. Mismo caso que ya se cuidó en document.py.
    assert "title" in props["metadata"]["properties"]


def test_esquema_openai_es_estricto():
    schema = openai_schema()
    assert schema["additionalProperties"] is False
    assert schema["required"] == list(schema["properties"].keys())


def test_el_draft_es_mas_chico_que_el_spec():
    """La IA no genera currículum, accesibilidad, fallbacks ni privacidad.

    Es lo que sostiene el presupuesto de 25 s: menos campos que emitir, menos
    tokens, menos riesgo de truncado por max_tokens.
    """
    campos_draft = set(LessonDraft.model_fields)
    campos_spec = set(LessonSpec.model_fields)
    assert campos_draft < campos_spec
    for garantia in ("curriculum", "accessibility", "fallbacks", "privacy"):
        assert garantia in campos_spec and garantia not in campos_draft


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
