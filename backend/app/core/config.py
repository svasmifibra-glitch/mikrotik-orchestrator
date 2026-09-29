import os
from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "MikroTik Cloud Orchestrator"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "mikrotik_super_secret_jwt_key_change_me_in_production_2026")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database setting: SQLite fallback for easy local/VPS demo, PostgreSQL for Vercel/Production
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./mikrotik_orchestrator.db")
    
    # Platform settings
    SERVER_HOST: str = os.getenv("SERVER_HOST", "http://localhost:8000")
    CORS_ORIGINS: List[str] = ["*"]
    
    # RouterOS default agent polling interval in seconds
    AGENT_POLL_INTERVAL: int = int(os.getenv("AGENT_POLL_INTERVAL", "300"))
    
    class Config:
        case_sensitive = True

settings = Settings()
