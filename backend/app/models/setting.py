from app.database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    openai_api_key = Column(String, nullable=True)
    google_api_key = Column(String, nullable=True)
    xai_api_key = Column(String, nullable=True)
    preferred_provider = Column(String, default="gemini")  # gemini | openai | xai
    gemini_model = Column(String, default="gemini-2.5-flash")
    gemini_image_model = Column(String, default="gemini-2.0-flash-preview-image-generation")
    openai_model = Column(String, default="gpt-4o")
    xai_model = Column(String, default="grok-3-mini")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="settings")
