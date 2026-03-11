from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.setting import Setting
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingsUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    preferred_provider: Optional[str] = "gemini"  # gemini | openai | xai
    gemini_model: Optional[str] = None
    gemini_image_model: Optional[str] = None
    openai_model: Optional[str] = None
    xai_model: Optional[str] = None

def mask_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]

@router.get("/")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    setting = db.query(Setting).filter(Setting.user_id == current_user.id).first()
    if not setting:
        return {
            "has_openai": False,
            "has_google": False,
            "has_xai": False,
            "openai_api_key_masked": None,
            "google_api_key_masked": None,
            "xai_api_key_masked": None,
            "preferred_provider": "gemini",
            "gemini_model": "gemini-2.5-flash",
            "gemini_image_model": "gemini-2.5-flash-image",
            "openai_model": "gpt-4o",
            "xai_model": "grok-3-mini",
        }
    return {
        "has_openai": bool(setting.openai_api_key),
        "has_google": bool(setting.google_api_key),
        "has_xai": bool(setting.xai_api_key),
        "openai_api_key_masked": mask_key(setting.openai_api_key),
        "google_api_key_masked": mask_key(setting.google_api_key),
        "xai_api_key_masked": mask_key(setting.xai_api_key),
        "preferred_provider": setting.preferred_provider or "gemini",
        "gemini_model": setting.gemini_model or "gemini-2.5-flash",
        "gemini_image_model": setting.gemini_image_model or "gemini-2.5-flash-image",
        "openai_model": setting.openai_model or "gpt-4o",
        "xai_model": setting.xai_model or "grok-3-mini",
    }

@router.put("/")
def update_settings(
    data: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    setting = db.query(Setting).filter(Setting.user_id == current_user.id).first()
    if not setting:
        setting = Setting(user_id=current_user.id)
        db.add(setting)

    # Only update key if a non-empty value is provided (avoid overwriting with placeholder)
    if data.openai_api_key and not data.openai_api_key.startswith("****"):
        setting.openai_api_key = data.openai_api_key.strip()
    if data.google_api_key and not data.google_api_key.startswith("****"):
        setting.google_api_key = data.google_api_key.strip()
    if data.xai_api_key and not data.xai_api_key.startswith("****"):
        setting.xai_api_key = data.xai_api_key.strip()
    if data.preferred_provider:
        setting.preferred_provider = data.preferred_provider
    if data.gemini_model:
        setting.gemini_model = data.gemini_model
    if data.gemini_image_model:
        setting.gemini_image_model = data.gemini_image_model
    if data.openai_model:
        setting.openai_model = data.openai_model
    if data.xai_model:
        setting.xai_model = data.xai_model

    db.commit()
    return {"message": "Configuración guardada correctamente"}

@router.delete("/keys")
def delete_keys(
    provider: str,  # openai | google | all
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    setting = db.query(Setting).filter(Setting.user_id == current_user.id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    if provider in ("openai", "all"):
        setting.openai_api_key = None
    if provider in ("google", "all"):
        setting.google_api_key = None
    if provider in ("xai", "all"):
        setting.xai_api_key = None
    db.commit()
    return {"message": "Clave eliminada"}

def get_user_settings(user_id: int, db: Session):
    """Helper to load API keys for a given user (used by ai_constructor)."""
    import os
    setting = db.query(Setting).filter(Setting.user_id == user_id).first()
    openai_key = (setting.openai_api_key if setting else None) or os.getenv("OPENAI_API_KEY", "")
    google_key = (setting.google_api_key if setting else None) or os.getenv("GOOGLE_API_KEY", "")
    xai_key = (setting.xai_api_key if setting else None) or os.getenv("XAI_API_KEY", "")
    preferred = (setting.preferred_provider if setting else None) or "gemini"
    gemini_model = (setting.gemini_model if setting else None) or "gemini-2.5-flash"
    gemini_image_model = (setting.gemini_image_model if setting else None) or "gemini-2.0-flash-preview-image-generation"
    openai_model = (setting.openai_model if setting else None) or "gpt-4o"
    xai_model = (setting.xai_model if setting else None) or "grok-3-mini"
    return openai_key, google_key, preferred, xai_key, gemini_model, openai_model, xai_model, gemini_image_model
