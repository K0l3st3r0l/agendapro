from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.database import get_db
from app.models.event import Event
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/events", tags=["events"])

CATEGORY_COLORS = {
    "general": "#6B7280",
    "reunion": "#3B82F6",
    "evaluacion": "#EF4444",
    "pendiente": "#F59E0B",
    "recordatorio": "#8B5CF6",
    "planificacion": "#10B981",
    "feriado": "#EC4899",
}

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    all_day: bool = False
    color: Optional[str] = None
    category: str = "general"
    location: Optional[str] = None
    alert_minutes: Optional[int] = None
    recurrence: Optional[str] = None

class EventUpdate(EventCreate):
    pass

class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    start_datetime: datetime
    end_datetime: Optional[datetime]
    all_day: bool
    color: str
    category: str
    location: Optional[str]
    alert_minutes: Optional[int]
    recurrence: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

@router.get("/", response_model=List[EventResponse])
def get_events(
    start: Optional[str] = None,
    end: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Event).filter(Event.user_id == current_user.id)
    if start:
        query = query.filter(Event.start_datetime >= datetime.fromisoformat(start))
    if end:
        query = query.filter(Event.start_datetime <= datetime.fromisoformat(end))
    if category:
        query = query.filter(Event.category == category)
    return query.order_by(Event.start_datetime).all()

@router.post("/", response_model=EventResponse)
def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    color = event.color or CATEGORY_COLORS.get(event.category, "#6B7280")
    db_event = Event(
        user_id=current_user.id,
        color=color,
        **{k: v for k, v in event.dict().items() if k != "color"}
    )
    db_event.color = color
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    event: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    for key, value in event.dict(exclude_unset=True).items():
        setattr(db_event, key, value)
    if not event.color:
        db_event.color = CATEGORY_COLORS.get(event.category, "#6B7280")
    db.commit()
    db.refresh(db_event)
    return db_event

@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    db.delete(db_event)
    db.commit()
    return {"message": "Evento eliminado"}

@router.get("/upcoming", response_model=List[EventResponse])
def get_upcoming_events(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from datetime import timedelta
    now = datetime.utcnow()
    end = now + timedelta(days=days)
    return (
        db.query(Event)
        .filter(Event.user_id == current_user.id)
        .filter(Event.start_datetime >= now)
        .filter(Event.start_datetime <= end)
        .order_by(Event.start_datetime)
        .all()
    )
