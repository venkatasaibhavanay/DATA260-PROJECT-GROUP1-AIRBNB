"""Configuration for the Messaging & Reviews Service.

Values come from environment variables or the repository-root .env file
(see shared/config.py). Never hardcode credentials here.
"""
from pydantic import Field

from shared.config import InfraSettings


class Settings(InfraSettings):
    service_name: str = "messaging-review-service"
    service_title: str = "Messaging & Reviews Service"
    service_description: str = "Guest-host messaging and property/user reviews."
    service_owner: str = "Srija Taduri"
    port: int = Field(default=8131, validation_alias="MESSAGING_REVIEW_SERVICE_PORT")

    # External systems this service is expected to use. Only probed by
    # GET /health/dependencies, never by GET /health.
    dependencies: tuple[str, ...] = ('mongodb', 'kafka')


settings = Settings()
