from app.database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    doc_type = Column(String, nullable=False)  # prueba, evaluacion, guia, planificacion, ficha
    subject = Column(String, nullable=True)    # Matemáticas, Lenguaje, Ciencias, etc.
    grade_level = Column(String, nullable=True) # 1°básico, 2°básico, etc.
    content = Column(JSON, nullable=True)       # structured content blocks
    raw_html = Column(Text, nullable=True)      # rendered HTML
    ai_prompt = Column(Text, nullable=True)     # original prompt used
    images = Column(JSON, nullable=True)        # list of generated image URLs
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="documents")
