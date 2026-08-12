from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.curriculum_oa import CurriculumOA
from app.models.user import User
from app.services.curriculum_context import fetch_indicators, fetch_oa
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


@router.get("/levels")
def get_levels(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Niveles y asignaturas que tienen OA cargados.

    El frontend lo usa para mostrar el selector de OA solo donde hay datos,
    en vez de ofrecer un desplegable vacío.
    """
    rows = (
        db.query(
            CurriculumOA.grade_level,
            CurriculumOA.subject,
            func.count(CurriculumOA.id).label("total"),
        )
        .group_by(CurriculumOA.grade_level, CurriculumOA.subject)
        .all()
    )

    levels: dict[str, list[dict]] = {}
    for grade_level, subject, total in rows:
        levels.setdefault(grade_level, []).append({"subject": subject, "count": total})

    return {
        "levels": [
            {"grade_level": grade, "subjects": sorted(subjects, key=lambda s: s["subject"])}
            for grade, subjects in sorted(levels.items())
        ]
    }


@router.get("/oa")
def get_oa(
    grade_level: str = Query(..., description="Ej: '1° Básico'"),
    subject: str = Query(..., description="Ej: 'Lenguaje y Comunicación'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = fetch_oa(db, grade_level, subject)
    indicadores = fetch_indicators(db, [r.id for r in rows])
    return {
        "grade_level": grade_level,
        "subject": subject,
        "oa": [
            {
                # El `id` es la única identificación real: 'OA11' existe en cuatro
                # asignaturas distintas de 1° Básico. Las clases visuales lo
                # guardan en su spec para que cambiar la asignatura en el editor
                # no re-apunte la clase a otro objetivo en silencio.
                "id": r.id,
                "code": r.code,
                "description": r.description,
                # Lista vacía cuando el Programa de Estudio no trae indicadores
                # para ese OA: no se rellena con nada generado.
                "indicators": [
                    {"id": i.id, "text": i.text, "ordinal": i.ordinal, "source": i.source}
                    for i in indicadores.get(r.id, [])
                ],
            }
            for r in rows
        ],
    }
