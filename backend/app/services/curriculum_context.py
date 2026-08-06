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

from app.models.curriculum_oa import CurriculumOA

MAX_OA_EN_CONTEXTO = 12


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

    listado = "\n".join(f"- {row.code}: {row.description}" for row in rows)
    disponibles = ", ".join(row.code for row in rows)

    return (
        "\n\nCURRÍCULUM OFICIAL MINEDUC — Objetivos de Aprendizaje de "
        f"{subject}, {grade_level}:\n{listado}\n\n"
        "REGLAS SOBRE EL CURRÍCULUM:\n"
        "- El contenido debe apuntar a los OA listados arriba.\n"
        f"- En metadata.oa_codes incluye únicamente códigos de esta lista: {disponibles}.\n"
        "- No inventes códigos OA ni cites objetivos que no aparezcan arriba.\n"
        "- Si un OA no calza con el tema pedido, simplemente no lo incluyas.\n"
    )


def valid_codes(db: Session, grade_level: str, subject: str) -> set[str]:
    """Códigos realmente existentes, para descartar los que el modelo invente."""
    rows = (
        db.query(CurriculumOA.code)
        .filter(CurriculumOA.grade_level == grade_level, CurriculumOA.subject == subject)
        .all()
    )
    return {row[0] for row in rows}
