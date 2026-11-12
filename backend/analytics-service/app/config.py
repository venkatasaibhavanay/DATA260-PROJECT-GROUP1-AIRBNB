"""Configuration for the Analytics & Observability Service.

Values come from environment variables or the repository-root .env file
(see shared/config.py). Never hardcode credentials here.
"""
from pydantic import Field

from shared.config import InfraSettings


class Settings(InfraSettings):
    service_name: str = "analytics-service"
    service_title: str = "Analytics & Observability Service"
    service_description: str = "Event analytics, metrics, and observability dashboards."
    service_owner: str = "Eric Zhao"
    port: int = Field(default=8151, validation_alias="ANALYTICS_SERVICE_PORT")

    # External systems this service is expected to use. Only probed by
    # GET /health/dependencies, never by GET /health.
    dependencies: tuple[str, ...] = ('mysql', 'mongodb', 'kafka')


settings = Settings()
