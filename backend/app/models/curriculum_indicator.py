from datetime import datetime

from app.database import Base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint


class CurriculumIndicator(Base):
    """Indicador de Evaluación oficial MINEDUC, colgado de un OA.

    Vienen de los Programas de Estudio, no de las Bases Curriculares: son la
    bajada observable del OA y por eso permiten anclar preguntas concretas.
    `source_ref` guarda el PDF y la página, para poder auditar cualquier fila
    contra el documento original.
    """

    __tablename__ = "curriculum_indicator"
    __table_args__ = (UniqueConstraint("oa_id", "ordinal", name="uq_curriculum_indicator"),)

    id = Column(Integer, primary_key=True, index=True)
    oa_id = Column(
        Integer, ForeignKey("curriculum_oa.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text = Column(Text, nullable=False)
    ordinal = Column(Integer, nullable=False)
    source = Column(String(20), nullable=False, default="mineduc")
    source_ref = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
