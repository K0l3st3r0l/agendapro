from app.database import Base
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from datetime import datetime

class CurriculumOA(Base):
    __tablename__ = "curriculum_oa"
    __table_args__ = (UniqueConstraint("grade_level", "subject", "code", name="uq_curriculum_oa"),)

    id = Column(Integer, primary_key=True, index=True)
    grade_level = Column(String(50), nullable=False, index=True)
    subject = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
