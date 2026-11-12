"""Service metadata and health endpoints.

Health semantics:
  GET /health               -> the application process is up. Does NOT check
                               databases, Redis, or Kafka.
  GET /health/dependencies  -> actively probes this service's external
                               dependencies; returns 503 if any are down.
"""
from fastapi import APIRouter, Response

from app.config import settings
from shared.dependencies import check_dependencies

router = APIRouter(tags=["health"])


@router.get("/")
def root():
    return {
        "service": settings.service_name,
        "title": settings.service_title,
        "description": settings.service_description,
        "owner": settings.service_owner,
        "docs": "/docs",
    }


@router.get("/health")
def health():
    return {
        "service": settings.service_name,
        "status": "ok",
        "scope": "application",
        "dependencies": "not_checked",
        "detail": "Application process is running. External dependencies are "
                  "not checked here; use GET /health/dependencies.",
    }


@router.get("/health/dependencies")
def health_dependencies(response: Response):
    results = check_dependencies(settings, settings.dependencies)
    healthy = all(r["status"] == "ok" for r in results.values())
    response.status_code = 200 if healthy else 503
    return {
        "service": settings.service_name,
        "status": "ok" if healthy else "degraded",
        "scope": "dependencies",
        "dependencies": results,
    }
