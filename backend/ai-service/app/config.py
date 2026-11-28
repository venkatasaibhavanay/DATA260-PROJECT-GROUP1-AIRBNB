"""Configuration for the Agentic AI & Recommendations Service.

Values come from environment variables or the repository-root .env file
(see shared/config.py). Never hardcode credentials here.
"""
from pydantic import Field

from shared.config import InfraSettings


class Settings(InfraSettings):
    service_name: str = "ai-service"
    service_title: str = "Agentic AI & Recommendations Service"
    service_description: str = "Agentic AI workflows and recommendations coordinated through Kafka."
    service_owner: str = "Angela Wai"
    port: int = Field(default=8141, validation_alias="AI_SERVICE_PORT")

    # External systems this service is expected to use. Only probed by
    # GET /health/dependencies, never by GET /health.
    dependencies: tuple[str, ...] = ('mongodb', 'redis', 'kafka')


settings = Settings()
