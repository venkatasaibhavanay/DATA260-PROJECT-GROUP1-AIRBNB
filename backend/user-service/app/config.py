"""Configuration for the User & Host Service.

Values come from environment variables or the repository-root .env file
(see shared/config.py). Never hardcode credentials here.
"""
from pathlib import Path

from pydantic import Field

from shared.config import InfraSettings


class Settings(InfraSettings):
    service_name: str = "user-service"
    service_title: str = "User & Host Service"
    service_description: str = "User accounts, guest and host profiles, authentication."
    service_owner: str = "Nathan Pak"
    port: int = Field(default=8101, validation_alias="USER_SERVICE_PORT")

    # External systems this service is expected to use. Only probed by
    # GET /health/dependencies, never by GET /health.
    dependencies: tuple[str, ...] = ('mysql', 'redis', 'kafka')

    # Uploaded profile photos, served at /media (env USER_MEDIA_ROOT).
    media_root: str = Field(default=str(Path(__file__).resolve().parents[1] / "media"),
                            validation_alias="USER_MEDIA_ROOT")


settings = Settings()
