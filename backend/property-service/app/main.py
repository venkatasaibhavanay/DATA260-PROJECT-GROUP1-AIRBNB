"""FastAPI entry point for the Property & Search Service.

Run locally from the repository root:
    ./scripts/start-service.sh property-service
Swagger UI: http://localhost:8111/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import health
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
# Add feature routers here, e.g.:
# from app.routes import properties
# app.include_router(properties.router, prefix="/api/v1/properties")
