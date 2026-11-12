"""Configuration for the Booking & Reservations Service.

Values come from environment variables or the repository-root .env file
(see shared/config.py). Never hardcode credentials here.
"""
from pydantic import Field

from shared.config import InfraSettings


class Settings(InfraSettings):
    service_name: str = "booking-service"
    service_title: str = "Booking & Reservations Service"
    service_description: str = "Booking requests, approvals, cancellations, and reservation lifecycle."
    service_owner: str = "Venkata Sai Bhavana Yarrapragada"
    port: int = Field(default=8121, validation_alias="BOOKING_SERVICE_PORT")

    # External systems this service is expected to use. Only probed by
    # GET /health/dependencies, never by GET /health.
    dependencies: tuple[str, ...] = ('mysql', 'redis', 'kafka')


settings = Settings()
