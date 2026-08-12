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

from fastapi import APIRouter, Depends, HTTPException
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

# El draft no incluye currículum resuelto ni las garantías del servidor, así que
# es bastante más chico que el spec completo. 6000 deja el doble de margen sobre
# una clase de 5 escenas medida con la fixture, sin regalar latencia: un truncado
# por max_tokens produce JSON inválido y gatilla el reintento, que es justo lo
# que el presupuesto de tiempo no aguanta.
MAX_TOKENS = 6000
TEMPERATURE = 0.6

# El modelo del Constructor (deepseek-v4-flash) no sirve acá: medido con este
# mismo prompt rinde ~65 tokens/s y tarda entre 42 y 92 s en emitir la clase,
# contra un presupuesto de 25 s. No es el esquema ni el razonamiento —es
# throughput— y la variabilidad es tan mala como la lentitud. gemini-2.5-flash
# hace el mismo trabajo a ~184 tokens/s. Solo aplica cuando la llamada sale por
# OpenRouter; con un proveedor directo manda la configuración de la profesora.
# Medición en wiki: projects/agendapro/decisions/modelo-storyboard-clases.
LESSONS_OPENROUTER_MODEL = os.getenv("LESSONS_OPENROUTER_MODEL", "google/gemini-2.5-flash")


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

LA CLASE TIENE CINCO ESCENAS, una de cada tipo, en este orden:
concept → example → process → quiz → recap.

Seis es el máximo absoluto y solo si el contenido lo justifica de verdad. No \
agregues escenas para alargar: una clase de 45 minutos son cinco ideas bien \
explicadas, no ocho a medias. Siempre termina en "recap".

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

    partes.append(REGLAS_ESCENAS)
    partes.append(_reglas_de_nivel(req.grade_level))
    return "\n\n".join(partes)


async def _generar_validado(
    settings, prompt: str, grade_level: str, provider: Optional[str]
) -> tuple[LessonDraft, providers.GenerationResult]:
    """Genera y valida. Un reintento con el error como feedback, y basta.

    Mismo patrón que `_generate_validated()` del Constructor, que ya está
    probado en producción: el esquema garantiza JSON sintácticamente válido,
    no que la clase tenga sentido. Las reglas por tipo de escena y los límites
    de longitud por nivel solo se pueden comprobar después.
    """

    async def pedir(texto: str) -> providers.GenerationResult:
        return await providers.generate_json(
            settings,
            prompt=texto,
            system=SYSTEM_PROMPT,
            provider=provider,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            gemini_schema=lesson_schema.gemini_schema,
            openai_schema=lesson_schema.openai_schema,
            schema_name="clase_visual",
            openrouter_model=LESSONS_OPENROUTER_MODEL,
        )

    costo_previo = 0.0
    try:
        result = await pedir(prompt)
        costo_previo = result.cost
        draft = LessonDraft(**result.content)
        validate_semantics(draft, grade_level)
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
        logger.warning("Storyboard no parseable en el primer intento: %s", exc.detail)
    except (ValidationError, ValueError) as exc:
        primer_error = str(exc)
        logger.warning("Storyboard inválido en el primer intento: %s", primer_error)

    retry = await pedir(
        f"{prompt}\n\n"
        "El intento anterior no cumplió las reglas. Errores concretos:\n"
        f"{primer_error}\n"
        "Corrige SOLO eso y responde de nuevo con el JSON completo y válido."
    )
    retry.cost += costo_previo

    try:
        draft = LessonDraft(**retry.content)
        validate_semantics(draft, grade_level)
        return draft, retry
    except (ValidationError, ValueError) as segundo_error:
        # Falla visible: entregar media clase inválida es peor que no entregar
        # nada, porque la profesora se entera recién frente al curso.
        logger.warning("Storyboard inválido en el segundo intento: %s", segundo_error)
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
    draft, result = await _generar_validado(settings, prompt, req.grade_level, req.provider)
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
    return {**_resumen(fila), "spec": fila.spec}


@router.get("/{lesson_id}/present", response_model=dict)
async def presentar_clase(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Versión para el proyector: sin notas privadas.

    Se filtran en el backend y no en el frontend a propósito. Si la respuesta las
    llevara, ya habrían viajado al navegador y bastaría abrir la consola delante
    del curso para leerlas.
    """
    fila = _buscar(db, lesson_id, current_user.id)
    return {
        "id": fila.id,
        "title": fila.title,
        "spec": lesson_schema.public_spec(LessonSpec(**fila.spec)),
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

    pendientes = {a.query: a.style for a in spec.assets if a.status != "ready" and a.query}
    if not pendientes:
        return {"resueltos": 0, "pendientes": 0, "message": "Las imágenes ya estaban listas."}

    settings = get_user_settings(current_user.id, db)
    urls = await images.generate_images(settings, pendientes)

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
            asset.source = "builtin" if url.endswith(".svg") else "arasaac"
            if asset.source == "arasaac":
                asset.credit = "Pictogramas de ARASAAC (CC BY-NC-SA), Gobierno de Aragón"
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
