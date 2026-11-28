"""FastAPI entry point for the User & Host Service.

Run locally from the repository root:
    ./scripts/start-service.sh user-service
Swagger UI: http://localhost:8101/docs
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import auth, guests, health, hosts
from shared.errors import register_exception_handlers

app = FastAPI(
    title=settings.service_title,
    description=f"{settings.service_description} (Owner: {settings.service_owner})",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(guests.router, prefix="/api/v1")
app.include_router(hosts.router, prefix="/api/v1")
app.include_router(hosts.photo_router, prefix="/api/v1")

# Uploaded profile photos (GET /media/profiles/<guests|hosts>/<id>.<jpg|png>).
Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")
