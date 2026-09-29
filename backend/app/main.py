import os
import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.security import get_password_hash
from app.models.models import User, Router, Backup, Task, Alert
from app.api.v1 import auth, routers, backups, tasks, agent, firmware, alerts

logger = logging.getLogger("main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(routers.router, prefix=settings.API_V1_STR)
app.include_router(backups.router, prefix=settings.API_V1_STR)
app.include_router(tasks.router, prefix=settings.API_V1_STR)
app.include_router(agent.router, prefix=settings.API_V1_STR)
app.include_router(firmware.router, prefix=settings.API_V1_STR)
app.include_router(alerts.router, prefix=settings.API_V1_STR)

@app.on_event("startup")
def startup_event():
    """Ensure database connection and default admin user initialization with retry logic"""
    db_connected = False
    for attempt in range(10):
        try:
            logger.info(f"Connecting to database (attempt {attempt + 1}/10)...")
            Base.metadata.create_all(bind=engine)
            
            db: Session = SessionLocal()
            admin = db.query(User).filter(User.email == "admin@mikrotik.cloud").first()
            if not admin:
                admin = User(
                    email="admin@mikrotik.cloud",
                    hashed_password=get_password_hash("admin123"),
                    full_name="System Administrator",
                    role="admin"
                )
                db.add(admin)
                db.commit()
                logger.info(">>> Created default administrator: admin@mikrotik.cloud / admin123")
            db.close()
            db_connected = True
            break
        except Exception as e:
            logger.warning(f"Database not ready yet ({e}). Retrying in 2 seconds...")
            time.sleep(2)
            
    if not db_connected:
        logger.error("Could not connect to database after 10 retries.")

# Mount Static directory for frontend bundle if present
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>MikroTik Cloud Orchestrator</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-white min-h-screen flex flex-col justify-center items-center font-sans">
        <div class="max-w-xl text-center p-8 bg-slate-800 rounded-2xl shadow-2xl border border-slate-700">
            <div class="w-16 h-16 bg-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 text-3xl font-bold shadow-lg">⚡</div>
            <h1 class="text-3xl font-extrabold mb-2">MikroTik Cloud Orchestrator</h1>
            <p class="text-slate-400 mb-6">Plataforma centralizada para gestión, monitoreo y actualización masiva de routers MikroTik RouterOS.</p>
            <div class="flex gap-4 justify-center">
                <a href="/docs" class="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl font-semibold transition">Documentación Swagger API</a>
            </div>
        </div>
    </body>
    </html>
    """
