from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Lesson(Base):
    """Clase visual proyectable.

    Separada de `Document`: ese modelo está hecho para imprimibles con
    exportación PDF/DOCX y vínculo textual con el calendario. Una clase necesita
    escenas ordenadas, preguntas referenciadas y notas que nunca se proyectan.

    El spec completo vive en un solo JSONB y su forma la garantiza Pydantic
    (`app/schemas/lesson.py`) antes de llegar acá. Las columnas sueltas de arriba
    son solo lo que necesita el listado para no deserializar el spec entero.
    """

    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    grade_level = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    schema_version = Column(String, nullable=False, default="1.0")
    spec = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="lessons")
