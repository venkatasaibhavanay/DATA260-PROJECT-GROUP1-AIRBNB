"""Common response shapes. See docs/API_CONVENTIONS.md."""
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    service: str
    status: Literal["ok", "degraded"]
    scope: Literal["application", "dependencies"]


class PageMeta(BaseModel):
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=100, default=20)
    total: int = Field(ge=0, default=0)
