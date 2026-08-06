"""Contexto curricular MINEDUC para anclar la generación.

La tabla `curriculum_oa` existía desde julio pero nunca se usó en los prompts:
la IA inventaba objetivos de aprendizaje sin ninguna relación con el nivel.

El patrón sigue lo que funcionó en el RAG del Reglamento Interno de Anahuac
(ver wiki: anahuac/bugs/reglamento-ia-alucinaciones): **el contexto va en el
mensaje del usuario, no en el system prompt**. Ponerlo en el system hacía que
el modelo lo tratara como un rol a interpretar en vez de datos a citar.

Los OA se cargan siempre desde la base de datos. Nunca se confía en el texto
que manda el cliente: si el frontend pudiera inyectar descripciones de OA, la
"validación curricular" no validaría nada.
"""

from sqlalchemy.orm import Session

from app.models.curriculum_indicator import CurriculumIndicator
from app.models.curriculum_oa import CurriculumOA

MAX_OA_EN_CONTEXTO = 12
# Los Programas de Estudio traen hasta 12 indicadores para un mismo OA. Volcarlos
# todos repite el problema que ya obligó a acotar los OA: el modelo reparte la
# atención y el documento termina rozando doce desempeños en vez de evaluar
# unos pocos. Seis alcanzan para cubrir el rango de dificultad del OA, que es
# como el propio Programa los ordena (de habilidades básicas a superiores).
MAX_INDICADORES_POR_OA = 6


def fetch_oa(
    db: Session,
    grade_level: str,
    subject: str,
    codes: list[str] | None = None,
) -> list[CurriculumOA]:
    query = db.query(CurriculumOA).filter(
        CurriculumOA.grade_level == grade_level,
        CurriculumOA.subject == subject,
    )
    if codes:
        query = query.filter(CurriculumOA.code.in_([c.strip().upper() for c in codes if c.strip()]))
    return query.order_by(CurriculumOA.id).all()


def fetch_indicators(db: Session, oa_ids: list[int]) -> dict[int, list[CurriculumIndicator]]:
    """{oa_id: [indicadores en orden]}. Una sola consulta para todos los OA."""
    if not oa_ids:
        return {}
    rows = (
        db.query(CurriculumIndicator)
        .filter(CurriculumIndicator.oa_id.in_(oa_ids))
        .order_by(CurriculumIndicator.oa_id, CurriculumIndicator.ordinal)
        .all()
    )
    agrupados: dict[int, list[CurriculumIndicator]] = {}
    for row in rows:
        agrupados.setdefault(row.oa_id, []).append(row)
    return agrupados


def build_context(
    db: Session,
    grade_level: str,
    subject: str,
    codes: list[str] | None = None,
) -> str:
    """Bloque de texto para inyectar en el prompt. Vacío si no hay OA cargados."""
    rows = fetch_oa(db, grade_level, subject, codes)
    if not rows:
        return ""

    # Sin selección explícita se acota el contexto: volcar 40 OA diluye la
    # atención del modelo y encarece la llamada sin mejorar el documento.
    if not codes:
        rows = rows[:MAX_OA_EN_CONTEXTO]

    # Los indicadores se cargan de la BD igual que los OA. El cliente no los
    # manda: si pudiera, el anclaje curricular dejaría de anclar nada.
    indicadores = fetch_indicators(db, [row.id for row in rows])

    bloques = []
    hay_indicadores = False
    for row in rows:
        bloques.append(f"- {row.code}: {row.description}")
        propios = indicadores.get(row.id, [])[:MAX_INDICADORES_POR_OA]
        if propios:
            hay_indicadores = True
            bloques.append(f"  Indicadores de evaluación oficiales de {row.code}:")
            bloques.extend(f"    · {ind.text}" for ind in propios)

    listado = "\n".join(bloques)
    disponibles = ", ".join(row.code for row in rows)

    reglas = [
        "- El contenido debe apuntar a los OA listados arriba.",
        f"- En metadata.oa_codes incluye únicamente códigos de esta lista: {disponibles}.",
        "- No inventes códigos OA ni cites objetivos que no aparezcan arriba.",
        "- Si un OA no calza con el tema pedido, simplemente no lo incluyas.",
    ]
    if hay_indicadores:
        reglas.append(
            "- Cada pregunta o actividad debe evaluar alguno de los indicadores listados "
            "para su OA. No inventes indicadores ni evalúes desempeños que no estén ahí; "
            "si un OA no trae indicadores, guíate solo por su enunciado."
        )

    return (
        "\n\nCURRÍCULUM OFICIAL MINEDUC — Objetivos de Aprendizaje de "
        f"{subject}, {grade_level}:\n{listado}\n\n"
        "REGLAS SOBRE EL CURRÍCULUM:\n" + "\n".join(reglas) + "\n"
    )


def valid_codes(db: Session, grade_level: str, subject: str) -> set[str]:
    """Códigos realmente existentes, para descartar los que el modelo invente."""
    rows = (
        db.query(CurriculumOA.code)
        .filter(CurriculumOA.grade_level == grade_level, CurriculumOA.subject == subject)
        .all()
    )
    return {row[0] for row in rows}
