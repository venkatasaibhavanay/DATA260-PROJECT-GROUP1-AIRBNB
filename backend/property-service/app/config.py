"""Configuration for the Property & Search Service.

Values come from environment variables or the repository-root .env file
(see shared/config.py). Never hardcode credentials here.
"""
from pydantic import Field

from shared.config import InfraSettings


class Settings(InfraSettings):
    service_name: str = "property-service"
    service_title: str = "Property & Search Service"
    service_description: str = "Property listings, availability metadata, and search."
    service_owner: str = "Sanjana Reddy Katham"
    port: int = Field(default=8111, validation_alias="PROPERTY_SERVICE_PORT")

    # External systems this service is expected to use. Only probed by
    # GET /health/dependencies, never by GET /health.
    dependencies: tuple[str, ...] = ('mysql', 'mongodb', 'redis', 'kafka')


settings = Settings()
