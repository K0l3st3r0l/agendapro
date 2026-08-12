"""LessonSpec v1 — contrato de una clase visual proyectable.

Reglas heredadas de `document.py`, que ya pagó el costo de descubrirlas:

- **Sin `Optional`.** Gemini rechaza `anyOf` en un `response_schema` y Pydantic
  lo genera para cualquier `Optional[X]`. Todo campo lleva un default concreto
  y el sentinel (cadena vacía, lista vacía, 0) se interpreta como "ausente".
- **Envelope de escena fijo.** Los cinco tipos comparten la misma forma y el
  mismo `data`; las reglas por tipo se aplican después en `validate_semantics()`.
  Una unión discriminada volvería a meter `anyOf`.
- **`extra="forbid"`.** Un campo inventado por el modelo es un error visible, no
  algo que se ignora en silencio.

Dos decisiones propias de este módulo:

**La IA llena `LessonDraft`, no `LessonSpec`.** El spec completo incluye el
currículum resuelto contra la BD, accesibilidad, fallbacks y privacidad: pedirle
todo eso al modelo cuesta tokens y latencia contra el presupuesto de 25 s, y
además dejaría en sus manos campos que deben ser garantías del servidor. El
modelo genera el contenido; `build_spec()` arma el documento.

**Los límites de longitud son diseño, no capricho.** Una plantilla de escena bien
diseñada se rompe igual con un `body` de 400 caracteres. El límite del campo es
el del rango 3°–8°; el de 1°–2°, más estrecho, lo aplica `validate_semantics()`
según el nivel — no se puede expresar en el schema estático porque depende del
curso.
"""

import re
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas._jsonschema import gemini_schema_for, openai_schema_for

SCHEMA_VERSION = "1.0"

SceneType = Literal["concept", "example", "process", "quiz", "recap"]
LessonKind = Literal["introduction", "development", "reinforcement", "closure"]
MotionPreset = Literal["none", "gentle-reveal", "step-by-step", "answer-reveal", "static"]
AssetKind = Literal["image", "svg_diagram", "icon"]
AssetStyle = Literal["none", "photo", "coloring"]
AssetSource = Literal["builtin", "arasaac", "generated"]
AssetStatus = Literal["pending", "ready", "failed"]
AssetFallback = Literal["alt_text", "static_diagram", "label"]
# Paletas y fondos decorativos diseñados a mano; el modelo solo elige cuál calza
# con el contenido. Mismo principio que las figuras: la IA declara intención, el
# frontend renderiza. Nunca CSS ni colores generados.
VisualTheme = Literal[
    "numeros", "naturaleza", "universo", "palabras",
    "comunidad", "cuerpo", "agua", "arte",
]

QuestionKind = Literal["single_choice"]
ResponseMode = Literal["oral", "written", "drawing"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Límites de contenido por nivel
# ---------------------------------------------------------------------------
# En 1°–2° la profesora dicta y los niños recién decodifican: la pantalla lleva
# imagen y muy poco texto. En 3°–8° se admite más densidad. Ver §3.4 y §5.3 del
# plan en wiki/projects/agendapro/plan-clases-visuales-implementacion.md.

# El largo se deriva de lo que cabe legible proyectado, no de una intuición: en
# 1024×768 —el peor proyector de sala que hay que soportar— una fuente de 5vh
# entra a unos 40–45 caracteres por línea. Una viñeta de dos líneas son ~80
# caracteres y se lee bien; el tope anterior de 50 obligaba a una línea y
# rechazaba contenido correcto de Lenguaje, que necesita frases más largas que
# Matemática.
#
# Lo que sí distingue a 1°–2° es la CANTIDAD de elementos, no su largo: tres
# ideas de cierre en vez de cinco. Esa es la carga cognitiva real; el largo de
# cada viñeta lo absorbe la profesora leyéndola en voz alta.
LIMITES = {
    "inicial": {
        "title": 45,
        "body": 90,
        "key_points": (3, 80),
        "steps": (2, 4),
        "examples": (1, 2),
        "question_prompt": 85,
        "option_label": 25,
        "options": (2, 3),
    },
    "estandar": {
        "title": 60,
        "body": 140,
        "key_points": (5, 110),
        "steps": (2, 5),
        "examples": (1, 3),
        "question_prompt": 120,
        "option_label": 40,
        "options": (2, 4),
    },
}

# Listas donde pasarse del tope no rompe nada: están ordenadas por importancia y
# quedarse con las primeras es una decisión de diseño defendible. Se recortan en
# `build_spec` en vez de rechazar la generación completa.
#
# Medido: los rechazos por "4 key_points en vez de 3" o "3 ejemplos en vez de 2"
# eran la mitad de los reintentos, y cada reintento duplica la latencia y el
# costo de la clase sin que hubiera nada malo en el contenido.
#
# `steps` NO está acá: truncar un procedimiento de cuatro pasos a tres lo deja
# incompleto y la escena deja de enseñar lo que dice enseñar. Ahí se prefiere
# admitir un paso más (el tope subió a 4) antes que cortar.

MIN_SCENES = 3
# Cinco es el default porque una clase de 45 minutos se sostiene con cinco ideas
# —una cada nueve minutos, contando la interacción con el curso—, y porque sin un
# techo el modelo entregaba 6 y hasta 8 escenas dispersando la clase.
#
# Pero es la profesora quien decide: un tema que necesita más desarrollo puede
# pedir más láminas. El tope de 10 no es arbitrario: por sobre eso la latencia de
# generación se dispara y una clase de 45 minutos ya no alcanza a cubrirlas.
ESCENAS_POR_DEFECTO = 5
MAX_SCENES = 10


def rango_escenas(pedidas: int = 0) -> tuple[int, int]:
    """Mínimo y máximo aceptados para el número de escenas que pidió la profesora.

    Se deja un grado de holgura hacia arriba: si pide 7 y el modelo entrega 8
    porque el contenido lo pedía, rechazar la clase entera sería desproporcionado
    —la misma lógica que con los `key_points`.
    """
    if not pedidas:
        return MIN_SCENES, MAX_SCENES
    objetivo = max(MIN_SCENES, min(pedidas, MAX_SCENES))
    return objetivo, min(objetivo + 1, MAX_SCENES)
MAX_PALABRAS_QUERY = 3

_GRADE_NUM = re.compile(r"(\d+)")


# Mundo por asignatura, para las clases guardadas antes de que existieran los
# mundos visuales. Sin esto una clase de Lenguaje se proyecta con la paleta azul
# de Matemática, que es el default del campo. Solo se usa cuando el spec no trae
# `visual_theme`: en las clases nuevas lo elige la IA por el contenido, que
# afina más que la asignatura.
_MUNDO_POR_ASIGNATURA = {
    "matemática": "numeros",
    "lenguaje": "palabras",
    "ciencias naturales": "naturaleza",
    "historia": "comunidad",
    "educación física": "cuerpo",
    "artes": "arte",
    "música": "arte",
    "tecnología": "numeros",
    "orientación": "cuerpo",
    "inglés": "palabras",
}


def mundo_por_asignatura(subject: str) -> str:
    s = (subject or "").lower()
    for clave, mundo in _MUNDO_POR_ASIGNATURA.items():
        if clave in s:
            return mundo
    return "numeros"


def completar_mundo_visual(spec: dict) -> dict:
    """Rellena `visual_theme` en specs anteriores al campo, sin tocar la BD."""
    metadata = spec.get("metadata") or {}
    if not metadata.get("visual_theme"):
        metadata["visual_theme"] = mundo_por_asignatura(
            (spec.get("curriculum") or {}).get("subject", "")
        )
        spec["metadata"] = metadata
    return spec


def nivel_de(grade_level: str) -> str:
    """'inicial' para 1° y 2° Básico, 'estandar' para el resto.

    Ante un `grade_level` que no se puede parsear se devuelve 'estandar': es el
    límite permisivo, y equivocarse hacia allá deja pasar una escena cargada en
    vez de rechazar una clase válida de 5° por no entender el string.
    """
    match = _GRADE_NUM.search(grade_level or "")
    if not match:
        return "estandar"
    return "inicial" if int(match.group(1)) <= 2 and "básico" in (grade_level or "").lower() else "estandar"


# ---------------------------------------------------------------------------
# Piezas de escena
# ---------------------------------------------------------------------------

class Step(Strict):
    id: str = Field("", max_length=40, description="Identificador único del paso dentro de la escena.")
    label: str = Field("", max_length=30, description="Nombre corto del paso, ej. 'Observa'.")
    description: str = Field("", max_length=120, description="Qué se hace en este paso, en una frase.")
    asset_ids: List[str] = Field(default_factory=list, description="IDs de assets declarados en el manifest.")


class Example(Strict):
    id: str = Field("", max_length=40)
    label: str = Field("", max_length=30, description="Etiqueta corta del ejemplo.")
    text: str = Field("", max_length=140, description="El ejemplo, concreto y cotidiano.")
    asset_ids: List[str] = Field(default_factory=list)


class SceneData(Strict):
    """Forma única para los cinco tipos de escena.

    Cada tipo usa unos pocos campos y deja el resto vacío; `validate_semantics()`
    verifica que los que corresponden estén llenos. Un `anyOf` por tipo sería más
    expresivo pero Gemini lo rechaza.
    """

    goal: str = Field("", max_length=200, description="Objetivo de la clase. Solo en la primera escena.")
    examples: List[Example] = Field(default_factory=list, description="Solo para type='example'.")
    steps: List[Step] = Field(default_factory=list, description="Solo para type='process'.")
    question_ref: str = Field("", max_length=40, description="ID de la pregunta. Obligatorio en type='quiz'.")
    key_points: List[str] = Field(default_factory=list, description="Solo para type='recap'.")
    prompt: str = Field("", max_length=140, description="Pregunta para la clase, dicha en voz alta.")


class Motion(Strict):
    preset: MotionPreset = Field("gentle-reveal")
    duration_ms: int = Field(500, ge=0, le=2000)
    stagger_ms: int = Field(0, ge=0, le=500)


class Scene(Strict):
    id: str = Field("", max_length=40, description="Identificador único de la escena.")
    type: SceneType = Field("concept")
    title: str = Field("", max_length=60, description="Título proyectado.")
    body: str = Field(
        "",
        max_length=140,
        description=(
            "Texto proyectado. UNA sola idea. En 1° y 2° Básico, máximo 90 caracteres "
            "y palabras que un niño de 6 años pueda leer."
        ),
    )
    narration: str = Field(
        "",
        max_length=600,
        description=(
            "Qué dice la profesora en voz alta en esta escena. No se proyecta. Aquí va "
            "la explicación completa: la pantalla muestra poco, la voz explica."
        ),
    )
    duration_seconds: int = Field(60, ge=15, le=600)
    asset_ids: List[str] = Field(default_factory=list)
    motion: Motion = Field(default_factory=Motion)
    data: SceneData = Field(default_factory=SceneData)
    teacher_note: str = Field(
        "",
        max_length=400,
        description="Instrucción operativa para la profesora, ej. 'reparte los círculos antes de esta escena'. No se proyecta.",
    )


# ---------------------------------------------------------------------------
# Assets y preguntas
# ---------------------------------------------------------------------------

class AssetIntent(Strict):
    """Lo que el modelo declara: qué imagen hace falta, no la imagen.

    `uri`, `source`, `status` y `credit` no están acá a propósito. El modo
    estricto de OpenAI exige que `required` liste *todas* las propiedades, así
    que cualquier campo del esquema el modelo lo emite sí o sí — y esos cuatro
    el servidor los sobrescribe igual. Eran tokens de salida pagados y
    esperados para nada, con el agravante de que una `uri` inventada por la IA
    es exactamente lo que el pipeline de imágenes existe para evitar.
    """

    id: str = Field("", max_length=40)
    kind: AssetKind = Field("image")
    role: str = Field("", max_length=40, description="Para qué sirve en la escena.")
    query: str = Field(
        "",
        max_length=60,
        description="Sustantivo concreto y visual para buscar o generar la imagen. Nunca una frase.",
    )
    style: AssetStyle = Field(
        "none",
        description="Déjalo en 'none'. La clase se proyecta a color; 'coloring' es para imprimir.",
    )
    alt: str = Field("", max_length=140, description="Descripción textual, obligatoria.")
    fallback: AssetFallback = Field("alt_text")


class Asset(AssetIntent):
    """La intención más lo que resuelve el backend."""

    uri: str = ""
    source: AssetSource = "generated"
    status: AssetStatus = "pending"
    credit: str = ""


class Option(Strict):
    id: str = Field("", max_length=40)
    label: str = Field("", max_length=40, description="Texto de la alternativa. Corto: se compara de un vistazo.")
    asset_id: str = Field(
        "",
        max_length=40,
        description=(
            "Asset que ilustra la alternativa. En 1° y 2° Básico las alternativas deberían "
            "ser imágenes: con solo texto la pregunta mide lectura, no contenido."
        ),
    )


class Question(Strict):
    id: str = Field("", max_length=40)
    kind: QuestionKind = Field("single_choice")
    prompt: str = Field("", max_length=120)
    options: List[Option] = Field(default_factory=list)
    correct_option_ids: List[str] = Field(default_factory=list)
    explanation: str = Field("", max_length=200, description="Por qué la respuesta es correcta.")
    feedback_correct: str = Field("", max_length=120)
    feedback_incorrect: str = Field("", max_length=120)


# ---------------------------------------------------------------------------
# Bloques del docente
# ---------------------------------------------------------------------------

class TeacherNotes(Strict):
    before_class: str = Field("", max_length=600, description="Materiales y preparación.")
    during_class: str = Field("", max_length=600)
    after_class: str = Field("", max_length=600)


class RubricLevel(Strict):
    level: str = Field("", max_length=40)
    evidence: str = Field("", max_length=200)


class ExitAssessment(Strict):
    enabled: bool = Field(True)
    prompt: str = Field("", max_length=200, description="Ticket de salida.")
    response_mode: ResponseMode = Field("oral")
    expected_evidence: str = Field("", max_length=200)
    rubric: List[RubricLevel] = Field(default_factory=list)


class LessonMetadata(Strict):
    title: str = Field("", max_length=60)
    topic: str = Field("", max_length=120)
    lesson_kind: LessonKind = Field("introduction")
    visual_theme: VisualTheme = Field(
        "numeros",
        description=(
            "Mundo visual de la clase, elegido por su CONTENIDO y no por la asignatura: "
            "numeros (cantidades, formas, patrones), naturaleza (plantas, animales, seres vivos), "
            "universo (día y noche, astros, luz, tiempo), palabras (lectura, escritura, letras, cuentos), "
            "comunidad (familia, oficios, historia, convivencia, señales), cuerpo (salud, emociones, sentidos), "
            "agua (mar, lluvia, clima, ciclo del agua), arte (música, colores, dibujo)."
        ),
    )


# ---------------------------------------------------------------------------
# Lo que genera la IA
# ---------------------------------------------------------------------------

class LessonDraft(Strict):
    """Lo único que se le pide al proveedor.

    Deliberadamente no incluye currículum resuelto, accesibilidad, fallbacks ni
    privacidad: son garantías del servidor y pedirlas costaría tokens contra el
    presupuesto de 25 s sin ganar nada.
    """

    metadata: LessonMetadata = Field(default_factory=LessonMetadata)
    scenes: List[Scene] = Field(default_factory=list)
    questions: List[Question] = Field(default_factory=list)
    assets: List[AssetIntent] = Field(default_factory=list)
    teacher_notes: TeacherNotes = Field(default_factory=TeacherNotes)
    exit_assessment: ExitAssessment = Field(default_factory=ExitAssessment)


# ---------------------------------------------------------------------------
# Lo que completa el servidor
# ---------------------------------------------------------------------------

class ResolvedOA(Strict):
    """Snapshot del OA con su PK real.

    `code` no identifica un OA: 'OA11' existe en Lenguaje, Matemática, Ciencias
    Naturales e Historia de 1° Básico. Guardar `oa_id` evita que editar la
    asignatura en el editor re-apunte la clase a otro objetivo en silencio.
    """

    oa_id: int = 0
    code: str = ""
    text: str = ""


class ResolvedIndicator(Strict):
    indicator_id: int = 0
    ref: str = ""
    oa_code: str = ""
    ordinal: int = 0
    text: str = ""
    source_ref: str = ""


class Curriculum(Strict):
    grade_level: str = ""
    subject: str = ""
    unit: str = ""
    oa_refs: List[str] = Field(default_factory=list)
    indicator_refs: List[str] = Field(default_factory=list)
    resolved_oas: List[ResolvedOA] = Field(default_factory=list)
    resolved_indicators: List[ResolvedIndicator] = Field(default_factory=list)


class MotionDefaults(Strict):
    enabled: bool = True
    preset: MotionPreset = "gentle-reveal"
    max_duration_ms: int = 1200


class Accessibility(Strict):
    language: str = "es-CL"
    alt_text_required: bool = True
    announce_scene_changes: bool = True
    keyboard: bool = True
    touch: bool = True
    reduced_motion: str = "respect"


class Fallbacks(Strict):
    missing_asset: str = "show_alt_text"
    unsupported_motion: str = "show_final_state"
    unsupported_scene: str = "render_text_card"


class Privacy(Strict):
    student_data_allowed: bool = False
    response_storage: str = "none"


class LessonSpec(Strict):
    schema_version: str = SCHEMA_VERSION
    spec_type: str = "lesson"
    curriculum: Curriculum = Field(default_factory=Curriculum)
    metadata: LessonMetadata = Field(default_factory=LessonMetadata)
    duration_minutes: int = Field(45, ge=10, le=180)
    audience: str = ""
    assets: List[Asset] = Field(default_factory=list)
    motion_defaults: MotionDefaults = Field(default_factory=MotionDefaults)
    scenes: List[Scene] = Field(default_factory=list)
    questions: List[Question] = Field(default_factory=list)
    teacher_notes: TeacherNotes = Field(default_factory=TeacherNotes)
    exit_assessment: ExitAssessment = Field(default_factory=ExitAssessment)
    accessibility: Accessibility = Field(default_factory=Accessibility)
    fallbacks: Fallbacks = Field(default_factory=Fallbacks)
    privacy: Privacy = Field(default_factory=Privacy)


# ---------------------------------------------------------------------------
# Validación semántica
# ---------------------------------------------------------------------------

_REQUISITOS_POR_TIPO = {
    "concept": "un body con la idea central",
    "example": "al menos un ejemplo en data.examples",
    "process": "pasos en data.steps",
    "quiz": "un data.question_ref que apunte a una pregunta existente",
    "recap": "puntos en data.key_points",
}


def validate_semantics(draft: LessonDraft, grade_level: str, escenas_pedidas: int = 0) -> None:
    """Reglas que el schema estático no puede expresar.

    Junta *todos* los errores en un solo `ValueError` en vez de fallar en el
    primero: el mensaje se le devuelve al modelo como feedback del reintento, y
    corregir de a un error por vuelta gastaría llamadas de más.
    """
    limites = LIMITES[nivel_de(grade_level)]
    errores: List[str] = []

    minimo, maximo = rango_escenas(escenas_pedidas)
    if not (minimo <= len(draft.scenes) <= maximo):
        errores.append(f"La clase debe tener entre {minimo} y {maximo} escenas, tiene {len(draft.scenes)}.")

    ids_escena = [s.id for s in draft.scenes]
    if len(set(ids_escena)) != len(ids_escena):
        errores.append("Hay IDs de escena repetidos; cada escena necesita un id único.")

    ids_pregunta = {q.id for q in draft.questions}
    if len(ids_pregunta) != len(draft.questions):
        errores.append("Hay IDs de pregunta repetidos.")

    ids_asset = {a.id for a in draft.assets}
    if len(ids_asset) != len(draft.assets):
        errores.append("Hay IDs de asset repetidos.")

    for asset in draft.assets:
        if not asset.id:
            errores.append("Hay un asset sin id.")
        if not asset.alt:
            errores.append(f"El asset '{asset.id}' no tiene alt; es obligatorio.")
        # La query no se valida: se normaliza en `build_spec`. Rechazar una clase
        # entera —y pagar otra generación— porque una búsqueda de imagen trae
        # cuatro palabras es desproporcionado; es un dato auxiliar que el
        # servidor puede arreglar solo. Medido: era la causa de 2 de cada 3
        # rechazos, sin que ninguna de esas clases tuviera un problema real.

    tipos_vistos = set()
    for i, escena in enumerate(draft.scenes, 1):
        donde = f"Escena {i} ('{escena.id or 'sin id'}', tipo {escena.type})"
        tipos_vistos.add(escena.type)

        if not escena.id:
            errores.append(f"{donde}: falta el id.")
        if len(escena.title) > limites["title"]:
            errores.append(
                f"{donde}: el título tiene {len(escena.title)} caracteres y el máximo para "
                f"{grade_level} es {limites['title']}."
            )
        if len(escena.body) > limites["body"]:
            errores.append(
                f"{donde}: el body tiene {len(escena.body)} caracteres y el máximo para "
                f"{grade_level} es {limites['body']}. Acorta el texto proyectado y mueve la "
                f"explicación larga a narration."
            )

        for asset_id in escena.asset_ids:
            if asset_id not in ids_asset:
                errores.append(f"{donde}: referencia el asset '{asset_id}', que no está en la lista de assets.")

        if escena.type == "concept" and not escena.body:
            errores.append(f"{donde}: necesita {_REQUISITOS_POR_TIPO['concept']}.")

        elif escena.type == "example":
            minimo, _ = limites["examples"]
            # El exceso se recorta en `build_spec`; acá solo importa que haya.
            if len(escena.data.examples) < minimo:
                errores.append(
                    f"{donde}: necesita al menos {minimo} ejemplo en data.examples."
                )

        elif escena.type == "process":
            minimo, maximo = limites["steps"]
            if not (minimo <= len(escena.data.steps) <= maximo):
                errores.append(
                    f"{donde}: debe traer entre {minimo} y {maximo} pasos en data.steps, "
                    f"trae {len(escena.data.steps)}."
                )
            for paso in escena.data.steps:
                if not paso.description:
                    errores.append(f"{donde}: hay un paso sin description.")

        elif escena.type == "quiz":
            if not escena.data.question_ref:
                errores.append(f"{donde}: necesita {_REQUISITOS_POR_TIPO['quiz']}.")
            elif escena.data.question_ref not in ids_pregunta:
                errores.append(
                    f"{donde}: data.question_ref='{escena.data.question_ref}' no corresponde a "
                    f"ninguna pregunta declarada."
                )

        elif escena.type == "recap":
            _, largo = limites["key_points"]
            if not escena.data.key_points:
                errores.append(f"{donde}: necesita {_REQUISITOS_POR_TIPO['recap']}.")
            # El exceso de puntos se recorta en `build_spec`. El largo de cada
            # punto sí se exige: un punto de 80 caracteres no cabe proyectado en
            # 1° Básico, y recortarlo a la mitad lo dejaría sin sentido.
            for punto in escena.data.key_points:
                if len(punto) > largo:
                    errores.append(f"{donde}: el punto '{punto[:30]}…' supera los {largo} caracteres.")

    if "recap" not in tipos_vistos:
        errores.append("La clase debe cerrar con una escena de tipo 'recap'.")

    for pregunta in draft.questions:
        donde = f"Pregunta '{pregunta.id or 'sin id'}'"
        if not pregunta.id:
            errores.append("Hay una pregunta sin id.")
        if len(pregunta.prompt) > limites["question_prompt"]:
            errores.append(
                f"{donde}: el enunciado tiene {len(pregunta.prompt)} caracteres y el máximo para "
                f"{grade_level} es {limites['question_prompt']}."
            )

        minimo, maximo = limites["options"]
        if not (minimo <= len(pregunta.options) <= maximo):
            errores.append(
                f"{donde}: debe tener entre {minimo} y {maximo} alternativas, tiene {len(pregunta.options)}."
            )

        ids_opcion = {o.id for o in pregunta.options}
        if len(ids_opcion) != len(pregunta.options):
            errores.append(f"{donde}: hay IDs de alternativa repetidos.")

        for opcion in pregunta.options:
            if len(opcion.label) > limites["option_label"]:
                errores.append(
                    f"{donde}: la alternativa '{opcion.label[:20]}…' supera los "
                    f"{limites['option_label']} caracteres permitidos en {grade_level}."
                )
            if opcion.asset_id and opcion.asset_id not in ids_asset:
                errores.append(f"{donde}: la alternativa '{opcion.id}' referencia un asset inexistente.")

        if not pregunta.correct_option_ids:
            errores.append(f"{donde}: no declara respuesta correcta.")
        for correcta in pregunta.correct_option_ids:
            if correcta not in ids_opcion:
                errores.append(f"{donde}: la respuesta correcta '{correcta}' no es una de sus alternativas.")

    # El ticket de salida es la única evidencia de aprendizaje de la clase. Con
    # `enabled=True` por defecto, dejarlo vacío pasaba silenciosamente y la
    # profesora se quedaba sin cierre evaluativo.
    if draft.exit_assessment.enabled and not draft.exit_assessment.prompt:
        errores.append(
            "exit_assessment está habilitado pero no trae prompt: escribe qué se le pide al "
            "estudiante para cerrar la clase, o ponlo en enabled=false."
        )

    if errores:
        raise ValueError("\n".join(f"- {e}" for e in errores))


# Códigos curriculares que el modelo copia del bloque de contexto y mete en el
# texto proyectado: "¿Qué mensaje nos transmite esta imagen? [OA1:2]". Al curso
# no le dice nada y ocupa el ancho del título. Se limpian en el servidor en vez
# de rechazar la generación: es cosmético, no un error de contenido.
_CODIGO_CURRICULAR = re.compile(r"\s*[\[\(]\s*[A-ZÑ]{2,4}\s*\d+\s*(?::\s*\d+\s*)?[\]\)]")


def limpiar_texto_proyectado(texto: str) -> str:
    return _CODIGO_CURRICULAR.sub("", texto or "").strip()


# Palabras que no aportan nada a una búsqueda de pictograma y sí gastan el cupo
# de términos útiles.
_RUIDO_QUERY = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "o",
    "en", "con", "para", "por", "que", "al", "a", "su", "sus", "hacer", "sobre",
}


def normalizar_query(query: str) -> str:
    """Deja una búsqueda de imagen usable a partir de lo que haya escrito el modelo.

    ARASAAC busca por término: 'pasos para hacer un patrón repetitivo' no
    devuelve nada, 'pasos patrón repetitivo' sí puede. Se normaliza en vez de
    rechazar la generación completa porque es un dato auxiliar —si igual no
    encuentra imagen, la escena cae al `alt` y sigue funcionando.
    """
    palabras = [p for p in query.split() if p.lower() not in _RUIDO_QUERY]
    if not palabras:
        palabras = query.split()
    return " ".join(palabras[:MAX_PALABRAS_QUERY])


def _limpiar_escena(escena: Scene) -> Scene:
    """Quita los códigos curriculares de lo que ve el curso.

    `narration` y `teacher_note` se dejan intactos: ahí la referencia sí le
    sirve a la profesora.
    """
    limpio = escena.model_copy(deep=True)
    limpio.title = limpiar_texto_proyectado(limpio.title)
    limpio.body = limpiar_texto_proyectado(limpio.body)
    limpio.data.prompt = limpiar_texto_proyectado(limpio.data.prompt)
    limpio.data.key_points = [limpiar_texto_proyectado(p) for p in limpio.data.key_points]
    for ejemplo in limpio.data.examples:
        ejemplo.text = limpiar_texto_proyectado(ejemplo.text)
    for paso in limpio.data.steps:
        paso.description = limpiar_texto_proyectado(paso.description)
    return limpio


def _recortar_escena(escena: Scene, limites: dict) -> Scene:
    """Deja la escena dentro de lo que cabe proyectado, sin rechazarla.

    Las listas vienen ordenadas por importancia, así que quedarse con las
    primeras es la misma decisión que tomaría la profesora al editar.
    """
    max_puntos, _ = limites["key_points"]
    _, max_ejemplos = limites["examples"]

    if len(escena.data.key_points) <= max_puntos and len(escena.data.examples) <= max_ejemplos:
        return escena

    recortada = escena.model_copy(deep=True)
    recortada.data.key_points = recortada.data.key_points[:max_puntos]
    recortada.data.examples = recortada.data.examples[:max_ejemplos]
    return recortada


def _limpiar_pregunta(pregunta: Question) -> Question:
    limpia = pregunta.model_copy(deep=True)
    limpia.prompt = limpiar_texto_proyectado(limpia.prompt)
    limpia.explanation = limpiar_texto_proyectado(limpia.explanation)
    for opcion in limpia.options:
        opcion.label = limpiar_texto_proyectado(opcion.label)
    return limpia


def build_spec(
    draft: LessonDraft,
    *,
    curriculum: Curriculum,
    duration_minutes: int,
    audience: str,
) -> LessonSpec:
    """Arma el spec completo: contenido del modelo + garantías del servidor."""
    limites = LIMITES[nivel_de(curriculum.grade_level)]
    return LessonSpec(
        curriculum=curriculum,
        metadata=draft.metadata,
        duration_minutes=duration_minutes,
        audience=audience,
        assets=[
            Asset(**{**intent.model_dump(), "query": normalizar_query(intent.query)})
            for intent in draft.assets
        ],
        scenes=[_limpiar_escena(_recortar_escena(e, limites)) for e in draft.scenes],
        questions=[_limpiar_pregunta(q) for q in draft.questions],
        teacher_notes=draft.teacher_notes,
        exit_assessment=draft.exit_assessment,
    )


def public_spec(spec: LessonSpec) -> dict:
    """Versión para el proyector: sin nada que la profesora no quiera mostrar.

    Se quita en el backend y no en el frontend a propósito: si la respuesta las
    lleva, ya viajaron al navegador y basta abrir la consola para leerlas.
    """
    data = spec.model_dump()
    data["teacher_notes"] = TeacherNotes().model_dump()
    for escena in data.get("scenes", []):
        escena["teacher_note"] = ""
    return data


def gemini_schema() -> dict:
    return gemini_schema_for(LessonDraft)


def openai_schema() -> dict:
    return openai_schema_for(LessonDraft)
