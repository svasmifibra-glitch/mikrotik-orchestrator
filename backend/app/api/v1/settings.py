import os
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.api.v1.auth import get_current_user, require_roles
from app.models.models import User

logger = logging.getLogger("settings")
router = APIRouter(prefix="/settings", tags=["Customization & Branding"])

SETTINGS_FILE = os.getenv("SETTINGS_FILE_PATH", "/app/data/platform_settings.json")
if not os.path.exists("/app/data"):
    # Local fallback
    SETTINGS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "platform_settings.json"))

DEFAULT_SETTINGS = {
    "platform_title": "MikroTik Cloud",
    "platform_subtitle": "Orchestrator v2.0",
    "logo_type": "icon", # "icon" or "image"
    "logo_icon": "⚡",
    "logo_image_url": "",
    "primary_color": "#6366f1", # Indigo
    "theme_preset": "indigo" # indigo, emerald, sky, purple, rose, amber
}

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_SETTINGS, **data}
        except Exception as e:
            logger.error(f"Error loading settings file: {e}")
    return DEFAULT_SETTINGS.copy()

def save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

class PlatformSettingsUpdate(BaseModel):
    platform_title: Optional[str] = None
    platform_subtitle: Optional[str] = None
    logo_type: Optional[str] = None
    logo_icon: Optional[str] = None
    logo_image_url: Optional[str] = None
    primary_color: Optional[str] = None
    theme_preset: Optional[str] = None

@router.get("/branding")
def get_branding():
    """Public endpoint to get current logo and color theme for all clients"""
    return load_settings()

@router.put("/branding")
def update_branding(payload: PlatformSettingsUpdate, current_user: User = Depends(require_roles("admin"))):
    """Admin-only endpoint to update logo, platform title, and color scheme"""
    current = load_settings()
    update_data = payload.dict(exclude_unset=True)
    for k, v in update_data.items():
        if v is not None:
            current[k] = v
    save_settings(current)
    return {"status": "saved", "settings": current}
