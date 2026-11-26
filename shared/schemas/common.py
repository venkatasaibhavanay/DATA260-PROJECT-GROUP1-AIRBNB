"""Common request/response shapes. See docs/API_CONVENTIONS.md."""
import math
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class StrictModel(BaseModel):
    """Base for request bodies: unknown fields are rejected with 422."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(BaseModel):
    service: str
    status: Literal["ok", "degraded"]
    scope: Literal["application", "dependencies"]


class PageParams(StrictModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


def make_page(items: list[T], page: int, page_size: int, total: int) -> Page[T]:
    total_pages = 0 if total == 0 else math.ceil(total / page_size)
    return Page[T](items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)


class PageMeta(BaseModel):
    """Deprecated: use Page[T] / make_page."""

    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=100, default=20)
    total: int = Field(ge=0, default=0)
