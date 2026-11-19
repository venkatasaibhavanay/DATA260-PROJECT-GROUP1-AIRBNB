"""Uniform error responses and request context for all services (API doc section 2.3).

Every error response has the shape:
    {"error": {"code": "...", "message": "...", "fields": {...} | null},
     "meta": {"request_id": "...", "trace_id": "..."}}

register_exception_handlers(app) also installs the request-context middleware,
which reads/creates X-Trace-ID and X-Request-ID, stores them on request.state
and echoes both headers on every response (including errors).
"""
import logging
import warnings
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("shared.errors")

TRACE_HEADER = "X-Trace-ID"
REQUEST_HEADER = "X-Request-ID"

HTTP_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "ROLE_FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "FILE_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
}

_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


class ErrorBody(BaseModel):
    code: str
    message: str
    fields: dict[str, Any] | None = None


class ResponseMeta(BaseModel):
    request_id: str
    trace_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody
    meta: ResponseMeta


class AppError(Exception):
    """Raise from services/routes for expected business errors.

    AppError(404, "PROPERTY_NOT_FOUND", "Property not found.", fields={"property_id": "..."})
    ``details=`` is accepted as a deprecated alias for ``fields``.
    """

    def __init__(self, status_code: int, code: str, message: str, fields: Any = None, *, details: Any = None):
        super().__init__(message)
        if details is not None:
            warnings.warn("AppError(details=...) is deprecated; use fields=", DeprecationWarning, stacklevel=2)
            if fields is None:
                fields = details
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields

    @property
    def details(self) -> Any:  # backwards compatibility
        return self.fields


# ---------- request context ----------

def get_trace_id(request: Request) -> str:
    tid = getattr(request.state, "trace_id", None)
    if not tid:
        tid = request.headers.get(TRACE_HEADER) or str(uuid4())
        request.state.trace_id = tid
    return tid


def get_request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = request.headers.get(REQUEST_HEADER) or str(uuid4())
        request.state.request_id = rid
    return rid


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = get_trace_id(request)      # headers are case-insensitive in Starlette
        request_id = get_request_id(request)
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - last-resort guard; body never has a stack trace
            logger.exception("unhandled_exception trace_id=%s", trace_id)
            response = _respond(request, 500, "INTERNAL_ERROR", "Unexpected server error.")
        response.headers[TRACE_HEADER] = trace_id
        response.headers[REQUEST_HEADER] = request_id
        return response


# ---------- error responses ----------

def _respond(request: Request, status: int, code: str, message: str, fields: Any = None) -> JSONResponse:
    trace_id = get_trace_id(request)
    request_id = get_request_id(request)
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, fields=fields),
        meta=ResponseMeta(request_id=request_id, trace_id=trace_id),
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(),
        headers={TRACE_HEADER: trace_id, REQUEST_HEADER: request_id},
    )


def validation_fields(errors: list[dict]) -> dict[str, str]:
    """{"check_out": "...", "guests.0.name": "..."} with the leading body/query/path removed."""
    out: dict[str, str] = {}
    for e in errors:
        loc = list(e.get("loc", []))
        if loc and loc[0] in _LOCATION_PREFIXES:
            loc = loc[1:]
        key = ".".join(str(p) for p in loc) or "_root"
        out.setdefault(key, str(e.get("msg", "Invalid value.")))
    return out


def register_exception_handlers(app: FastAPI) -> None:
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _respond(request, exc.status_code, exc.code, exc.message, exc.fields)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return _respond(request, 422, "VALIDATION_ERROR", "One or more fields are invalid.",
                        validation_fields(exc.errors()))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = HTTP_STATUS_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
        return _respond(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.error("unhandled_exception trace_id=%s", get_trace_id(request), exc_info=exc)
        return _respond(request, 500, "INTERNAL_ERROR", "Unexpected server error.")
