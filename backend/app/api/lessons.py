"""Clases visuales — generación del storyboard.

Módulo separado del Constructor a propósito: `ai_constructor.py` produce
documentos imprimibles (pruebas, guías, planificaciones) con exportación a
PDF/DOCX, y una clase proyectable necesita escenas, tiempos, notas privadas y
un player. Comparten proveedores, currículum, ajustes y autenticación; no
comparten contrato ni endpoints.

Lo que se genera acá es un `LessonDraft` —solo contenido—, no el `LessonSpec`
completo: el currículum se resuelve contra la base de datos y las garantías de
accesibilidad y privacidad las pone el servidor.
"""

import logging
import os
import time
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.settings import get_user_settings
from app.database import get_db
from app.models.lesson import Lesson
from app.models.user import User
from app.schemas import lesson as lesson_schema
from app.schemas.lesson import (
    Curriculum,
    LessonDraft,
    LessonSpec,
    ResolvedIndicator,
    ResolvedOA,
    build_spec,
    nivel_de,
    validate_semantics,
)
from app.services import curriculum_context, images, providers
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lessons", tags=["lessons"])

# El presupuesto de salida escala con las láminas pedidas: una clase de cinco
# escenas ocupa ~2.600 tokens medidos sobre la fixture, así que con diez el techo
# fijo de 6.000 truncaba el JSON y gatillaba el reintento. La profesora aceptó
# esperar hasta dos minutos, y un reintento cuesta mucho más que unos tokens de
# margen.
TOKENS_BASE = 2500
TOKENS_POR_ESCENA = 1300
TEMPERATURE = 0.6


def _max_tokens(escenas: int) -> int:
    return TOKENS_BASE + TOKENS_POR_ESCENA * max(escenas or lesson_schema.ESCENAS_POR_DEFECTO, 3)

# El modelo del Constructor (deepseek-v4-flash) no sirve acá: medido con este
# mismo prompt rinde ~65 tokens/s y tarda entre 42 y 92 s en emitir la clase,
# contra un presupuesto de 25 s. No es el esquema ni el razonamiento —es
# throughput— y la variabilidad es tan mala como la lentitud. gemini-2.5-flash
# hace el mismo trabajo a ~184 tokens/s. Solo aplica cuando la llamada sale por
# OpenRouter; con un proveedor directo manda la configuración de la profesora.
# Medición en wiki: projects/agendapro/decisions/modelo-storyboard-clases.
# Cascada, no un modelo único. Depender de uno solo significa que la profesora
# se queda sin poder preparar su clase cuando ese proveedor tiene un mal día,
# agota cuota o cambia de precio. Se prueban en orden y se pasa al siguiente
# ante cuota agotada, rate limit o indisponibilidad —nunca ante un error de
# contenido, que se corrige reintentando con el mismo modelo.
#
# Orden medido el 2026-08-12 con el mismo prompt (una corrida por modelo):
#
#   gpt-5.6-luna       27 s   $0,0019   válido
#   gemini-2.5-flash   20 s   $0,0087   válido
#   deepseek-v4-flash  217 s  $0,0006   INVÁLIDO (respuesta correcta apuntando
#                                        a otra pregunta)
#
# Luna va primero: calidad equivalente a Gemini y 4,6× más barato; los 7 s extra
# no significan nada contra el minuto y medio que la profesora igual espera por
# las imágenes. DeepSeek queda al final —es el más barato pero tardó 3,6 minutos
# y aun así falló la validación—; está solo como último recurso antes de dejar a
# la profesora sin clase.
LESSONS_OPENROUTER_MODELS = [
    m.strip() for m in os.getenv(
        "LESSONS_OPENROUTER_MODELS",
        "openai/gpt-5.6-luna,google/gemini-2.5-flash,deepseek/deepseek-v4-flash-0731",
    ).split(",") if m.strip()
]

# Estados en los que cambiar de modelo sí ayuda: el problema es el proveedor,
# no lo que le pedimos. Un 400 (clave inválida) o un 422 se repetirían igual.
ESTADOS_PARA_CAMBIAR_DE_MODELO = {402, 429, 503, 529}


SYSTEM_PROMPT = """Eres una profesora chilena de educación básica con veinte años de aula \
y experiencia en diseño de clases visuales.

Diseñas la CLASE PROYECTADA: lo que los estudiantes ven en el pizarrón digital o el \
telón mientras la profesora expone. No es una guía impresa ni una prueba.

Principios que respetas siempre:

1. UNA idea por escena. Si una escena necesita dos ideas, son dos escenas.
2. La pantalla muestra poco; la profesora explica. El texto proyectado es un ancla \
visual, no el contenido completo: lo que hay que decir va en `narration`.
3. Lenguaje chileno, cercano y correcto. Nunca "vos", "che", "ustedes" en su forma \
española peninsular ni modismos argentinos.
4. Ejemplos concretos y cotidianos del contexto chileno: el patio, la micro, la feria, \
la once, el kiosco del colegio.
5. Progresión real: se presenta la idea, se muestra un ejemplo, se enseña el \
procedimiento, se comprueba con una pregunta y se cierra recuperando lo aprendido.
6. Nunca inventas objetivos de aprendizaje ni indicadores. Trabajas solo con los que \
te entregan.
7. Nunca incluyes nombres, RUT, notas ni datos de estudiantes reales.

Respondes únicamente con el JSON del esquema pedido. Sin explicaciones, sin markdown, \
sin ```json."""


REGLAS_ESCENAS = """
TIPOS DE ESCENA DISPONIBLES (no existe ningún otro):

- "concept": presenta la idea central. Usa `body` para enunciarla y `narration` para \
explicarla. `data.goal` lleva el objetivo de la clase solo si es la primera escena.
- "example": muestra el contenido en una situación cotidiana. Llena `data.examples`.
- "process": enseña el procedimiento paso a paso. Llena `data.steps`; cada paso tiene \
`label` corto (una palabra de acción) y `description` de una frase.
- "quiz": comprueba la comprensión. `data.question_ref` debe traer el `id` de una \
pregunta declarada en `questions`.
- "recap": cierra la clase. Llena `data.key_points`.

{{ESCENAS}}

No agregues escenas para alargar ni repitas contenido para llegar al número: \
cada escena tiene que aportar una idea propia. Siempre termina en "recap".

REGLAS DE LOS CAMPOS DE TEXTO:

- `body` es lo que se proyecta. Es corto. Si necesitas explicar más, va en `narration`.
- `narration` es lo que la profesora dice en voz alta. Aquí sí desarrollas la \
explicación completa, con las palabras que usarías frente al curso.
- `teacher_note` es una instrucción operativa para ella (qué material repartir, cuándo \
esperar respuestas). Solo cuando aporte algo; vacío si no.

IMÁGENES:

- Declara en `assets` solo lo que las escenas usan, y referencia por `id` desde \
`asset_ids`.
- `query` es el OBJETO que se va a dibujar, no lo que la escena explica. Máximo 3 \
palabras. Se usa tal cual para buscar un pictograma: si no nombra una cosa concreta, \
no encuentra nada y la escena se queda sin imagen.
  Bien: "manzana", "collar de cuentas", "reloj", "círculo rojo".
  Mal: "pasos para hacer un patrón", "patrón incompleto", "niños aprendiendo".
  Una escena sobre los pasos de un procedimiento igual necesita un objeto: usa el \
objeto con el que se trabaja, no el nombre del procedimiento.
- `alt` es obligatorio en todos los assets.

CIERRE DE LA CLASE:

- `exit_assessment.prompt` es obligatorio: qué se le pide al estudiante para \
demostrar lo aprendido. Debe poder responderse en un minuto.
"""


def _instruccion_escenas(pedidas: int) -> str:
    """Cuántas láminas pedir, según lo que eligió la profesora."""
    if not pedidas:
        return (
            "LA CLASE TIENE CINCO ESCENAS, una de cada tipo, en este orden:\n"
            "concept → example → process → quiz → recap."
        )
    if pedidas <= 5:
        return (
            f"LA CLASE TIENE EXACTAMENTE {pedidas} ESCENAS. Elige los tipos que mejor "
            f"enseñen este contenido y cierra siempre con 'recap'."
        )
    # Con más de cinco hay que repetir tipos. Medido: pidiendo 6 sin esta regla,
    # el modelo devolvió tres 'concept' seguidos y ningún 'process' — tres
    # láminas que se ven y se sienten iguales, que es justo lo que las cinco
    # composiciones distintas existen para evitar.
    return (
        f"LA CLASE TIENE EXACTAMENTE {pedidas} ESCENAS.\n"
        f"Usa los CINCO tipos al menos una vez antes de repetir ninguno: una clase "
        f"con tres 'concept' seguidos son tres láminas que se ven iguales y el "
        f"curso desconecta. Recién después repite el tipo que el contenido pida, "
        f"con material distinto —dos 'example' con situaciones diferentes, un "
        f"segundo 'quiz' sobre otra cosa—. Cierra siempre con 'recap'."
    )


def _reglas_de_nivel(grade_level: str) -> str:
    """Instrucciones de longitud según el curso.

    Van en el prompt además de estar validadas: es más barato que el modelo
    acierte a la primera que corregirlo en el reintento.
    """
    limites = lesson_schema.LIMITES[nivel_de(grade_level)]
    inicial = nivel_de(grade_level) == "inicial"

    reglas = [
        "",
        f"LÍMITES ESTRICTOS PARA {grade_level} (se validan; si los superas la respuesta se rechaza):",
        f"- `title` de escena: máximo {limites['title']} caracteres.",
        f"- `body` de escena: máximo {limites['body']} caracteres.",
        f"- `data.key_points`: máximo {limites['key_points'][0]} puntos de {limites['key_points'][1]} caracteres.",
        f"- `data.steps`: entre {limites['steps'][0]} y {limites['steps'][1]} pasos.",
        f"- `data.examples`: entre {limites['examples'][0]} y {limites['examples'][1]} ejemplos.",
        f"- Enunciado de pregunta: máximo {limites['question_prompt']} caracteres.",
        f"- Alternativas: entre {limites['options'][0]} y {limites['options'][1]}, "
        f"de máximo {limites['option_label']} caracteres cada una.",
    ]

    if inicial:
        reglas += [
            "",
            "ESTE CURSO ES DE LECTORES INICIALES. Es la restricción que manda sobre todo lo demás:",
            "- Los niños tienen 6 o 7 años y recién están aprendiendo a leer.",
            "- La IMAGEN es el contenido; el texto solo la acompaña. Toda escena debe tener asset.",
            "- Palabras cortas y frecuentes. Frases de una línea. Nada de subordinadas.",
            "- Las alternativas de la pregunta DEBEN tener `asset_id`: si son solo texto, la "
            "pregunta mide lectura en vez de contenido.",
            "- `narration` en cambio puede ser larga: la profesora lee y explica en voz alta.",
        ]

    return "\n".join(reglas)


class StoryboardRequest(BaseModel):
    grade_level: str = Field(..., min_length=1, max_length=60)
    subject: str = Field(..., min_length=1, max_length=120)
    topic: str = Field(..., min_length=1, max_length=300)
    unit: str = Field("", max_length=200)
    duration_minutes: int = Field(45, ge=10, le=180)
    lesson_kind: str = Field("introduction")
    # 0 = la profesora no eligió; se usa el default de cinco.
    scene_count: int = Field(0, ge=0, le=lesson_schema.MAX_SCENES)
    oa_refs: List[str] = Field(default_factory=list)
    indicator_refs: List[str] = Field(default_factory=list)
    instructions: str = Field("", max_length=1500)
    provider: Optional[str] = None


def _resolver_curriculum(db: Session, req: StoryboardRequest) -> tuple[Curriculum, str]:
    """Snapshot curricular con las PK reales + el bloque de texto para el prompt.

    El cliente manda referencias; los textos salen siempre de la base de datos.
    Si el frontend pudiera mandar el enunciado de un OA, el anclaje curricular
    no anclaría nada.
    """
    ctx = curriculum_context.build_context(
        db, req.grade_level, req.subject, req.oa_refs, req.indicator_refs
    )

    if not req.oa_refs:
        # Sin selección explícita, `build_context` igual ofrece hasta 12 OA al
        # modelo para que se oriente, pero no sabemos cuál terminó cubriendo. El
        # snapshot queda vacío en vez de afirmar que la clase trabaja los treinta
        # OA de la asignatura, que es lo que devolvería `fetch_oa` sin filtro.
        return Curriculum(
            grade_level=req.grade_level, subject=req.subject, unit=req.unit
        ), ctx.block

    filas = curriculum_context.fetch_oa(db, req.grade_level, req.subject, req.oa_refs)
    if not filas:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No se encontraron los objetivos {', '.join(req.oa_refs)} en "
                f"{req.subject} de {req.grade_level}."
            ),
        )

    indicadores = curriculum_context.fetch_indicators(db, [f.id for f in filas])
    ordinales_pedidos = {
        ref.strip().upper() for ref in req.indicator_refs if ref.strip()
    }

    resolved_oas = [ResolvedOA(oa_id=f.id, code=f.code, text=f.description) for f in filas]
    resolved_indicators = []
    for fila in filas:
        for ind in indicadores.get(fila.id, []):
            ref = f"{fila.code.upper()}:{ind.ordinal}"
            if ordinales_pedidos and ref not in ordinales_pedidos:
                continue
            resolved_indicators.append(
                ResolvedIndicator(
                    indicator_id=ind.id,
                    ref=ref,
                    oa_code=fila.code,
                    ordinal=ind.ordinal,
                    text=ind.text,
                    source_ref=ind.source_ref or "",
                )
            )

    curriculum = Curriculum(
        grade_level=req.grade_level,
        subject=req.subject,
        unit=req.unit,
        oa_refs=[f.code for f in filas],
        indicator_refs=[i.ref for i in resolved_indicators],
        resolved_oas=resolved_oas,
        resolved_indicators=resolved_indicators,
    )
    return curriculum, ctx.block


def _build_prompt(req: StoryboardRequest, bloque_curricular: str) -> str:
    partes = [
        f"Diseña una clase visual proyectable de {req.subject} para {req.grade_level}.",
        f"TEMA: {req.topic}",
        f"DURACIÓN: {req.duration_minutes} minutos.",
        f"MOMENTO DE LA CLASE: {req.lesson_kind}.",
    ]
    if req.unit:
        partes.append(f"UNIDAD: {req.unit}")
    if bloque_curricular:
        partes.append(bloque_curricular)
    if req.instructions:
        partes.append(f"INDICACIONES DE LA PROFESORA (respétalas):\n{req.instructions}")

    partes.append(REGLAS_ESCENAS.replace("{{ESCENAS}}", _instruccion_escenas(req.scene_count)))
    partes.append(_reglas_de_nivel(req.grade_level))
    return "\n\n".join(partes)


async def _generar_validado(
    settings, prompt: str, grade_level: str, provider: Optional[str], escenas_pedidas: int = 0
) -> tuple[LessonDraft, providers.GenerationResult]:
    """Genera y valida. Un reintento con el error como feedback, y basta.

    Mismo patrón que `_generate_validated()` del Constructor, que ya está
    probado en producción: el esquema garantiza JSON sintácticamente válido,
    no que la clase tenga sentido. Las reglas por tipo de escena y los límites
    de longitud por nivel solo se pueden comprobar después.
    """

    async def pedir(texto: str, modelo: str) -> providers.GenerationResult:
        return await providers.generate_json(
            settings,
            prompt=texto,
            system=SYSTEM_PROMPT,
            provider=provider,
            max_tokens=_max_tokens(escenas_pedidas),
            temperature=TEMPERATURE,
            gemini_schema=lesson_schema.gemini_schema,
            openai_schema=lesson_schema.openai_schema,
            schema_name="clase_visual",
            openrouter_model=modelo,
        )

    costo_total = 0.0
    ultimo_de_proveedor: HTTPException | None = None

    for modelo in LESSONS_OPENROUTER_MODELS:
        try:
            draft, result = await _intentar_con(pedir, prompt, modelo, grade_level, escenas_pedidas)
            result.cost += costo_total
            return draft, result
        except HTTPException as exc:
            if exc.status_code in ESTADOS_PARA_CAMBIAR_DE_MODELO:
                # El proveedor está caído, sin cuota o limitando: otro modelo sí
                # puede responder. La profesora no tiene por qué quedarse sin
                # clase porque un proveedor tuvo un mal día.
                logger.warning("%s no está disponible (%s); probando el siguiente", modelo, exc.status_code)
                ultimo_de_proveedor = exc
                continue
            raise

    raise ultimo_de_proveedor or HTTPException(
        status_code=503,
        detail="Ningún proveedor de IA está disponible en este momento. Inténtalo en unos minutos.",
    )


async def _intentar_con(pedir, prompt: str, modelo: str, grade_level: str, escenas_pedidas: int):
    """Un modelo, hasta dos intentos: el segundo lleva los errores como feedback.

    Cambiar de modelo por un error de contenido no serviría —el problema es lo
    que pedimos, no quién responde—, así que el reintento va contra el mismo.
    """
    costo_previo = 0.0
    try:
        result = await pedir(prompt, modelo)
        costo_previo = result.cost
        draft = LessonDraft(**result.content)
        validate_semantics(draft, grade_level, escenas_pedidas)
        return draft, result
    except providers.InvalidJSONError as exc:
        # Un JSON cortado o malformado también merece el reintento. Antes se
        # propagaba desde `generate_json` sin pasar por acá, así que una
        # respuesta truncada mataba la request sin segunda oportunidad —y en la
        # medición real fue el modo de falla más frecuente, no un caso raro.
        primer_error = (
            f"{exc.detail} Devuelve el JSON completo y bien formado, y acorta el "
            f"contenido si es necesario."
        )
        logger.warning("[%s] storyboard no parseable en el primer intento: %s", modelo, exc.detail)
    except (ValidationError, ValueError) as exc:
        primer_error = str(exc)
        logger.warning("[%s] storyboard inválido en el primer intento: %s", modelo, primer_error)

    retry = await pedir(
        f"{prompt}\n\n"
        "El intento anterior no cumplió las reglas. Errores concretos:\n"
        f"{primer_error}\n"
        "Corrige SOLO eso y responde de nuevo con el JSON completo y válido.",
        modelo,
    )
    retry.cost += costo_previo

    try:
        draft = LessonDraft(**retry.content)
        validate_semantics(draft, grade_level, escenas_pedidas)
        return draft, retry
    except (ValidationError, ValueError) as segundo_error:
        # Falla visible: entregar media clase inválida es peor que no entregar
        # nada, porque la profesora se entera recién frente al curso.
        logger.warning("[%s] storyboard inválido en el segundo intento: %s", modelo, segundo_error)
        raise HTTPException(
            status_code=502,
            detail=(
                "El modelo devolvió una clase con estructura inválida dos veces seguidas. "
                "Prueba otra vez o cambia de proveedor en Configuración."
            ),
        ) from segundo_error


@router.post("/storyboard")
async def generar_storyboard(
    req: StoryboardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_user_settings(current_user.id, db)
    curriculum, bloque = _resolver_curriculum(db, req)
    prompt = _build_prompt(req, bloque)

    inicio = time.monotonic()
    draft, result = await _generar_validado(
        settings, prompt, req.grade_level, req.provider, req.scene_count
    )
    elapsed_ms = int((time.monotonic() - inicio) * 1000)

    spec = build_spec(
        draft,
        curriculum=curriculum,
        duration_minutes=req.duration_minutes,
        audience=req.grade_level,
    )

    # El tiempo se mide y se registra siempre: el criterio de aceptación del
    # módulo es que el storyboard aparezca en menos de 25 s, y sin la medición
    # en producción no hay forma de saber si se sigue cumpliendo.
    logger.info(
        "Storyboard generado: %s/%s — %d escenas, %d preguntas, %d assets, %d ms, costo $%.5f",
        result.provider,
        result.model,
        len(spec.scenes),
        len(spec.questions),
        len(spec.assets),
        elapsed_ms,
        result.cost,
    )

    return {
        "spec": spec.model_dump(),
        "provider_used": result.provider,
        "model_used": result.model,
        "cost": result.cost,
        "elapsed_ms": elapsed_ms,
        "curriculum_grounded": bool(bloque),
    }


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------
# Sin `revision` optimista ni 409: cada clase la edita su propia autora desde una
# pestaña. Un control de concurrencia acá sería costo sin beneficio; si algún día
# dos personas comparten una clase, se agrega entonces.


async def _resolver_assets_en_fondo(lesson_id: int, user_id: int) -> None:
    """Resuelve las imágenes de una clase sin que el cliente tenga que pedirlo.

    Antes esto dependía de una segunda llamada del frontend, y bastaba con que
    la profesora tuviera la pestaña abierta desde antes del despliegue, navegara
    rápido o fuera directo a presentar para que la clase quedara sin imágenes
    para siempre. La resolución es responsabilidad del servidor: el navegador no
    tiene por qué ser el que la garantice.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        fila = db.query(Lesson).filter(Lesson.id == lesson_id, Lesson.user_id == user_id).first()
        if not fila:
            return
        spec = LessonSpec(**lesson_schema.completar_mundo_visual(dict(fila.spec)))
        pendientes = {a.query: "photo" for a in spec.assets if a.status != "ready" and a.query}
        if not pendientes:
            return

        settings = get_user_settings(user_id, db)
        urls = await images.generate_images(
            settings, pendientes, preferir_ia=True, theme=spec.metadata.visual_theme
        )
        for asset in spec.assets:
            if asset.status == "ready":
                continue
            url = urls.get(asset.query)
            if url:
                asset.uri, asset.status = url, "ready"
                asset.source = "builtin" if url.endswith(".svg") else "generated"
            else:
                asset.status = "failed"

        # Se relee la fila: la profesora pudo haber guardado ediciones mientras
        # las imágenes se generaban, y perdérselas sería peor que no tener fotos.
        actual = db.query(Lesson).filter(Lesson.id == lesson_id, Lesson.user_id == user_id).first()
        if not actual:
            return
        vigente = dict(actual.spec)
        por_query = {a.query: a for a in spec.assets}
        for asset in vigente.get("assets", []):
            resuelto = por_query.get(asset.get("query"))
            if resuelto and resuelto.status == "ready":
                asset.update({"uri": resuelto.uri, "status": "ready", "source": resuelto.source})
        actual.spec = vigente
        flag_modified(actual, "spec")
        db.commit()
        listos = sum(1 for a in vigente.get("assets", []) if a.get("status") == "ready")
        logger.info("Imágenes de la clase %d resueltas en segundo plano: %d listas", lesson_id, listos)
    except Exception as exc:
        logger.warning("No se pudieron resolver las imágenes de la clase %d: %s", lesson_id, exc)
    finally:
        db.close()


class LessonSave(BaseModel):
    spec: LessonSpec
    status: str = Field("draft", max_length=20)


def _buscar(db: Session, lesson_id: int, user_id: int) -> Lesson:
    """Devuelve la clase o 404.

    404 y no 403 cuando es de otra persona: un 403 confirmaría que la clase
    existe, que es justo lo que no corresponde revelar.
    """
    fila = (
        db.query(Lesson)
        .filter(Lesson.id == lesson_id, Lesson.user_id == user_id)
        .first()
    )
    if not fila:
        raise HTTPException(status_code=404, detail="La clase no existe.")
    return fila


def _resumen(fila: Lesson) -> dict:
    """Lo que necesita la biblioteca, sin deserializar el spec completo."""
    return {
        "id": fila.id,
        "title": fila.title,
        "subject": fila.subject,
        "grade_level": fila.grade_level,
        "status": fila.status,
        "scenes": len((fila.spec or {}).get("scenes", [])),
        "created_at": fila.created_at,
        "updated_at": fila.updated_at,
    }


@router.post("", response_model=dict)
async def crear_clase(
    data: LessonSave,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    spec = data.spec
    fila = Lesson(
        user_id=current_user.id,
        title=spec.metadata.title or spec.metadata.topic or "Clase sin título",
        subject=spec.curriculum.subject,
        grade_level=spec.curriculum.grade_level,
        status=data.status,
        schema_version=spec.schema_version,
        spec=spec.model_dump(),
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    tareas.add_task(_resolver_assets_en_fondo, fila.id, current_user.id)
    return {"id": fila.id, "message": "Clase guardada"}


@router.get("", response_model=dict)
async def listar_clases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filas = (
        db.query(Lesson)
        .filter(Lesson.user_id == current_user.id)
        .order_by(Lesson.updated_at.desc())
        .all()
    )
    return {"lessons": [_resumen(f) for f in filas]}


@router.get("/{lesson_id}", response_model=dict)
async def obtener_clase(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Versión completa, con notas del docente. Es la que abre el editor."""
    fila = _buscar(db, lesson_id, current_user.id)
    return {**_resumen(fila), "spec": lesson_schema.completar_mundo_visual(dict(fila.spec))}


@router.get("/{lesson_id}/present", response_model=dict)
async def presentar_clase(
    lesson_id: int,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Versión para el proyector: sin notas privadas.

    Se filtran en el backend y no en el frontend a propósito. Si la respuesta las
    llevara, ya habrían viajado al navegador y bastaría abrir la consola delante
    del curso para leerlas.
    """
    fila = _buscar(db, lesson_id, current_user.id)
    spec = lesson_schema.completar_mundo_visual(dict(fila.spec))
    # Última red: si una clase llega al proyector sin imágenes, se disparan igual
    # para la próxima vez. No bloquea la presentación de hoy.
    if any(a.get("status") == "pending" for a in spec.get("assets", [])):
        tareas.add_task(_resolver_assets_en_fondo, lesson_id, current_user.id)
    return {
        "id": fila.id,
        "title": fila.title,
        "spec": lesson_schema.public_spec(LessonSpec(**spec)),
    }


@router.put("/{lesson_id}", response_model=dict)
async def actualizar_clase(
    lesson_id: int,
    data: LessonSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fila = _buscar(db, lesson_id, current_user.id)
    spec = data.spec
    fila.title = spec.metadata.title or spec.metadata.topic or fila.title
    fila.subject = spec.curriculum.subject
    fila.grade_level = spec.curriculum.grade_level
    fila.status = data.status
    fila.schema_version = spec.schema_version
    fila.spec = spec.model_dump()
    db.commit()
    return {"id": fila.id, "message": "Clase actualizada"}


class RegenerateRequest(BaseModel):
    """Indicación opcional para el nuevo intento.

    Regenerar sin poder decir qué cambiar es una lotería: se vuelve a tirar el
    dado esperando que salga mejor. Con una frase —"más simple", "usa ejemplos
    de la feria"— la profesora dirige el segundo intento en vez de repetirlo.
    """

    instructions: str = Field("", max_length=1500)


@router.post("/{lesson_id}/regenerate", response_model=dict)
async def regenerar_clase(
    lesson_id: int,
    data: RegenerateRequest,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Vuelve a proponer la clase con los mismos parámetros curriculares.

    Los parámetros salen del spec guardado —nivel, asignatura, tema, OA y número
    de láminas—, así que no hace falta recordar el formulario original.

    Reemplaza el contenido: lo que la profesora haya editado a mano se pierde. El
    frontend lo advierte antes de llamar acá.
    """
    fila = _buscar(db, lesson_id, current_user.id)
    anterior = LessonSpec(**fila.spec)

    req = StoryboardRequest(
        grade_level=anterior.curriculum.grade_level,
        subject=anterior.curriculum.subject,
        topic=anterior.metadata.topic or anterior.metadata.title or "Clase",
        unit=anterior.curriculum.unit,
        duration_minutes=anterior.duration_minutes,
        lesson_kind=anterior.metadata.lesson_kind,
        oa_refs=anterior.curriculum.oa_refs,
        indicator_refs=anterior.curriculum.indicator_refs,
        instructions=data.instructions,
        # Mismo número de láminas que tenía: la profesora ya lo eligió una vez.
        scene_count=len(anterior.scenes),
    )

    settings = get_user_settings(current_user.id, db)
    curriculum, bloque = _resolver_curriculum(db, req)
    prompt = _build_prompt(req, bloque)

    inicio = time.monotonic()
    draft, result = await _generar_validado(
        settings, prompt, req.grade_level, None, req.scene_count
    )
    elapsed_ms = int((time.monotonic() - inicio) * 1000)

    spec = build_spec(
        draft, curriculum=curriculum,
        duration_minutes=req.duration_minutes, audience=req.grade_level,
    )

    fila.title = spec.metadata.title or spec.metadata.topic or fila.title
    fila.spec = spec.model_dump()
    flag_modified(fila, "spec")
    db.commit()

    logger.info(
        "Clase %d regenerada: %s/%s — %d escenas, %d ms%s",
        lesson_id, result.provider, result.model, len(spec.scenes), elapsed_ms,
        f", indicación: {data.instructions[:60]}" if data.instructions else "",
    )
    tareas.add_task(_resolver_assets_en_fondo, fila.id, current_user.id)
    return {
        "id": fila.id,
        "spec": spec.model_dump(),
        "model_used": result.model,
        "elapsed_ms": elapsed_ms,
        "message": "Clase regenerada",
    }


@router.post("/{lesson_id}/assets", response_model=dict)
async def resolver_assets(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resuelve las imágenes de la clase y las guarda en el spec.

    Va aparte de la generación del storyboard a propósito: la profesora ve y
    revisa el contenido de inmediato, y las imágenes se resuelven después sin
    hacerla esperar. Para el vocabulario de 1° y 2° —figuras geométricas y
    sustantivos concretos— suele terminar en menos de un segundo y sin costo,
    porque se dibujan o salen de ARASAAC.

    Es idempotente: los assets ya resueltos no se vuelven a pedir.
    """
    fila = _buscar(db, lesson_id, current_user.id)
    spec = LessonSpec(**fila.spec)

    # Siempre a color: `coloring` entrega contorno negro para pintar en papel,
    # que es lo correcto en una guía imprimible del Constructor y lo peor
    # posible proyectado —un dibujo sin relleno se pierde en el telón—. El
    # modelo elegía "coloring" por su cuenta al ver que la clase es de primero
    # básico.
    pendientes = {a.query: "photo" for a in spec.assets if a.status != "ready" and a.query}
    if not pendientes:
        return {"resueltos": 0, "pendientes": 0, "message": "Las imágenes ya estaban listas."}

    settings = get_user_settings(current_user.id, db)
    # Las clases visuales prefieren la ilustración generada por sobre el
    # pictograma: se proyecta al curso y la paleta acompaña al tema de la clase.
    urls = await images.generate_images(
        settings, pendientes, preferir_ia=True, theme=spec.metadata.visual_theme
    )

    fallidos = 0
    for asset in spec.assets:
        if asset.status == "ready":
            continue
        url = urls.get(asset.query)
        if url:
            asset.uri = url
            asset.status = "ready"
            # Las figuras geométricas se dibujan acá mismo; lo demás puede venir
            # de ARASAAC, que exige atribución por su licencia CC BY-NC-SA.
            asset.source = "builtin" if url.endswith(".svg") else "generated"
        else:
            # `failed` no rompe la clase: el player muestra el texto alternativo.
            asset.status = "failed"
            fallidos += 1

    fila.spec = spec.model_dump()
    flag_modified(fila, "spec")
    db.commit()

    resueltos = sum(1 for a in spec.assets if a.status == "ready")
    logger.info(
        "Assets de la clase %d: %d listos, %d sin imagen", lesson_id, resueltos, fallidos
    )
    return {"resueltos": resueltos, "fallidos": fallidos, "spec": spec.model_dump()}


@router.delete("/{lesson_id}", response_model=dict)
async def borrar_clase(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fila = _buscar(db, lesson_id, current_user.id)
    db.delete(fila)
    db.commit()
    return {"message": "Clase eliminada"}
