import asyncio
import os
from dataclasses import dataclass, field
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.setting import Setting
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_TEXT_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_IMAGE_MODEL = "openai/gpt-image-2"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_XAI_MODEL = "grok-3-mini"

ProviderId = Literal["openrouter", "gemini", "openai", "xai"]


# ---------------------------------------------------------------------------
# AISettings
# ---------------------------------------------------------------------------

@dataclass
class AISettings:
    """Claves y modelos resueltos para un usuario.

    Reemplaza una tupla de 8 elementos que se desempacaba idénticamente en 5
    endpoints: agregar un proveedor obligaba a tocar los 5 y cualquier cambio
    de orden los rompía en silencio, sin error de tipos.
    """

    openrouter_key: str = ""
    text_model: str = DEFAULT_TEXT_MODEL
    image_model: str = DEFAULT_IMAGE_MODEL

    google_key: str = ""
    openai_key: str = ""
    xai_key: str = ""

    preferred: str = "openrouter"
    gemini_model: str = DEFAULT_GEMINI_MODEL
    openai_model: str = DEFAULT_OPENAI_MODEL
    xai_model: str = DEFAULT_XAI_MODEL

    def key_for(self, provider: str) -> str:
        return {
            "openrouter": self.openrouter_key,
            "gemini": self.google_key,
            "openai": self.openai_key,
            "xai": self.xai_key,
        }.get(provider, "")

    def model_for(self, provider: str) -> str:
        return {
            "openrouter": self.text_model,
            "gemini": self.gemini_model,
            "openai": self.openai_model,
            "xai": self.xai_model,
        }.get(provider, self.text_model)

    def available(self) -> list[str]:
        """Proveedores con clave, en orden de preferencia de uso."""
        return [p for p in ("openrouter", "gemini", "openai", "xai") if self.key_for(p)]


def get_user_settings(user_id: int, db: Session) -> AISettings:
    """Carga las claves del usuario, cayendo a las variables de entorno."""
    row = db.query(Setting).filter(Setting.user_id == user_id).first()

    def pick(column: str, env: str) -> str:
        stored = getattr(row, column, None) if row else None
        return (stored or os.getenv(env, "") or "").strip()

    def model(column: str, default: str) -> str:
        return (getattr(row, column, None) if row else None) or default

    return AISettings(
        openrouter_key=pick("openrouter_api_key", "OPENROUTER_API_KEY"),
        text_model=model("text_model", os.getenv("OPENROUTER_TEXT_MODEL") or DEFAULT_TEXT_MODEL),
        image_model=model("image_model", os.getenv("OPENROUTER_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL),
        google_key=pick("google_api_key", "GOOGLE_API_KEY"),
        openai_key=pick("openai_api_key", "OPENAI_API_KEY"),
        xai_key=pick("xai_api_key", "XAI_API_KEY"),
        preferred=model("preferred_provider", "openrouter"),
        gemini_model=model("gemini_model", DEFAULT_GEMINI_MODEL),
        openai_model=model("openai_model", DEFAULT_OPENAI_MODEL),
        xai_model=model("xai_model", DEFAULT_XAI_MODEL),
    )


# ---------------------------------------------------------------------------
# CRUD de configuración
# ---------------------------------------------------------------------------

class SettingsUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    text_model: Optional[str] = None
    image_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    preferred_provider: Optional[str] = None
    gemini_model: Optional[str] = None
    openai_model: Optional[str] = None
    xai_model: Optional[str] = None


def mask_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("/")
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = db.query(Setting).filter(Setting.user_id == current_user.id).first()
    resolved = get_user_settings(current_user.id, db)

    def stored(column: str) -> Optional[str]:
        return getattr(row, column, None) if row else None

    return {
        # `has_*` refleja si el proveedor es utilizable, venga la clave de la BD
        # o del entorno. La UI lo usa para no ofrecer proveedores sin clave.
        "has_openrouter": bool(resolved.openrouter_key),
        "has_google": bool(resolved.google_key),
        "has_openai": bool(resolved.openai_key),
        "has_xai": bool(resolved.xai_key),
        "openrouter_api_key_masked": mask_key(stored("openrouter_api_key")),
        "google_api_key_masked": mask_key(stored("google_api_key")),
        "openai_api_key_masked": mask_key(stored("openai_api_key")),
        "xai_api_key_masked": mask_key(stored("xai_api_key")),
        "preferred_provider": resolved.preferred,
        "text_model": resolved.text_model,
        "image_model": resolved.image_model,
        "gemini_model": resolved.gemini_model,
        "openai_model": resolved.openai_model,
        "xai_model": resolved.xai_model,
    }


@router.put("/")
def update_settings(
    data: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(Setting).filter(Setting.user_id == current_user.id).first()
    if not row:
        row = Setting(user_id=current_user.id)
        db.add(row)

    # Solo se escribe si llega un valor real: el frontend manda la versión
    # enmascarada ("AIza****pfNo") cuando el usuario no tocó el campo.
    for field_name in ("openrouter_api_key", "openai_api_key", "google_api_key", "xai_api_key"):
        value = getattr(data, field_name)
        if value and "****" not in value:
            setattr(row, field_name, value.strip())

    for field_name in (
        "preferred_provider",
        "text_model",
        "image_model",
        "gemini_model",
        "openai_model",
        "xai_model",
    ):
        value = getattr(data, field_name)
        if value:
            setattr(row, field_name, value.strip())

    db.commit()
    return {"message": "Configuración guardada correctamente"}


@router.delete("/keys")
def delete_keys(
    provider: str,  # openrouter | google | openai | xai | all
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(Setting).filter(Setting.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    columns = {
        "openrouter": "openrouter_api_key",
        "google": "google_api_key",
        "openai": "openai_api_key",
        "xai": "xai_api_key",
    }
    if provider == "all":
        for column in columns.values():
            setattr(row, column, None)
    elif provider in columns:
        setattr(row, columns[provider], None)
    else:
        raise HTTPException(status_code=400, detail=f"Proveedor desconocido: {provider}")
    db.commit()
    return {"message": "Clave eliminada"}


# ---------------------------------------------------------------------------
# Salud de las claves
# ---------------------------------------------------------------------------

# Una clave inválida guardada en BD dejaba la cuenta muerta sin ninguna señal:
# el usuario veía "error al generar" sin saber que su clave había caducado.
# Esto la prueba contra el proveedor y devuelve el motivo real.

_PROBES = {
    "openrouter": ("https://openrouter.ai/api/v1/key", "bearer"),
    "openai": ("https://api.openai.com/v1/models", "bearer"),
    "xai": ("https://api.x.ai/v1/models", "bearer"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models", "query"),
}


async def _probe(provider: str, key: str) -> dict:
    if not key:
        return {"status": "missing", "detail": "Sin clave configurada"}

    url, auth_style = _PROBES[provider]
    headers = {"Authorization": f"Bearer {key}"} if auth_style == "bearer" else {}
    params = {"key": key} if auth_style == "query" else None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers=headers, params=params)
    except Exception as exc:  # red caída, DNS, timeout
        return {"status": "error", "detail": f"No se pudo contactar al proveedor: {exc}"}

    if response.status_code == 200:
        result = {"status": "ok", "detail": "Clave válida"}
        if provider == "openrouter":
            # OpenRouter informa saldo restante; es útil mostrarlo antes de
            # que una generación falle por créditos agotados.
            data = (response.json() or {}).get("data") or {}
            limit, usage = data.get("limit"), data.get("usage")
            if limit is not None and usage is not None:
                result["detail"] = f"Clave válida — quedan ${max(limit - usage, 0):.2f}"
            elif usage is not None:
                result["detail"] = f"Clave válida — gastado ${usage:.2f}"
        return result

    if response.status_code in (401, 403):
        return {"status": "invalid", "detail": "Clave inválida o sin permisos"}
    if response.status_code == 402:
        return {"status": "no_credit", "detail": "Sin créditos disponibles"}
    if response.status_code == 429:
        return {"status": "quota", "detail": "Cuota agotada o rate limit alcanzado"}
    if response.status_code == 400 and provider == "gemini":
        # Google responde 400 API_KEY_INVALID en vez de 401.
        return {"status": "invalid", "detail": "Clave inválida o sin permisos"}
    return {"status": "error", "detail": f"Respuesta inesperada ({response.status_code})"}


@router.get("/health")
async def settings_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_user_settings(current_user.id, db)
    providers = list(_PROBES.keys())
    results = await asyncio.gather(
        *(_probe(p, settings.key_for(p)) for p in providers),
        return_exceptions=True,
    )

    report = {}
    for provider, result in zip(providers, results):
        if isinstance(result, Exception):
            report[provider] = {"status": "error", "detail": str(result)}
        else:
            report[provider] = result

    usable = [p for p, r in report.items() if r["status"] == "ok"]
    return {"providers": report, "usable": usable, "any_usable": bool(usable)}
