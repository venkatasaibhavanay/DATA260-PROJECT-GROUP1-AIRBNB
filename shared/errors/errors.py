"""Uniform error responses for all services.

Every error response has the shape:
    {"error": {"code": "BOOKING_NOT_FOUND", "message": "...", "details": {...}, "trace_id": "..."}}
"""
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

TRACE_HEADER = "X-Trace-Id"


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None
    trace_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """Raise from services/routes for expected business errors."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _trace_id(request: Request) -> str:
    return request.headers.get(TRACE_HEADER) or str(uuid4())


def _respond(request: Request, status: int, code: str, message: str, details: Any = None):
    trace_id = _trace_id(request)
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details, trace_id=trace_id))
    return JSONResponse(status_code=status, content=body.model_dump(), headers={TRACE_HEADER: trace_id})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _respond(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return _respond(request, 422, "VALIDATION_ERROR", "Request validation failed",
                        jsonable_errors(exc.errors()))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return _respond(request, exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))


def jsonable_errors(errors: list[dict]) -> list[dict]:
    return [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in errors]
