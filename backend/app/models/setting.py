from app.database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    # Pasarela principal: cubre texto e imágenes con una sola clave.
    openrouter_api_key = Column(String, nullable=True)
    text_model = Column(String, default="deepseek/deepseek-v4-flash")
    image_model = Column(String, default="google/gemini-3.1-flash-lite-image")

    # Proveedores directos, opcionales: solo se usan si el usuario pone su
    # propia clave. Ninguno es el camino por defecto.
    openai_api_key = Column(String, nullable=True)
    google_api_key = Column(String, nullable=True)
    xai_api_key = Column(String, nullable=True)
    preferred_provider = Column(String, default="openrouter")  # openrouter | gemini | openai | xai
    gemini_model = Column(String, default="gemini-2.5-flash")
    openai_model = Column(String, default="gpt-4o")
    xai_model = Column(String, default="grok-3-mini")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="settings")
