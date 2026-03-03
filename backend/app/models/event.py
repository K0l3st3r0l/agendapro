from app.database import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=True)
    all_day = Column(Boolean, default=False)
    color = Column(String, default="#3B82F6")  # Tailwind blue-500
    category = Column(String, default="general")  # general, reunion, evaluacion, pendiente, recordatorio
    location = Column(String, nullable=True)
    alert_minutes = Column(Integer, nullable=True)  # minutes before event
    recurrence = Column(String, nullable=True)  # none, daily, weekly, monthly
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="events")
