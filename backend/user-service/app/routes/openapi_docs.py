"""Swagger helpers: documented error responses with examples (documentation only)."""
from typing import Any

from shared.errors import ErrorResponse

_DESCRIPTIONS = {
    400: "Bad request", 401: "Missing, expired or invalid token", 403: "Not permitted",
    404: "Not found", 409: "Conflict", 413: "Upload too large", 415: "Unsupported media type",
    422: "Validation failed", 429: "Rate limit reached", 503: "Dependency unavailable; nothing was saved",
}

_META = {"request_id": "3f1b2c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d", "trace_id": "7f3c9a2e-1b4d-4e8a-9c6f-2d5b8e1a0c47"}

UNAUTHORIZED = (401, "UNAUTHORIZED", "Missing or invalid token.")
TOKEN_EXPIRED = (401, "TOKEN_EXPIRED", "Token expired.")
ROLE_FORBIDDEN = (403, "ROLE_FORBIDDEN", "This action is not allowed for your role.")
VALIDATION = (422, "VALIDATION_ERROR", "One or more fields are invalid.", {"phone": "Phone must be in E.164 format, for example +14085550101."})
EMAIL_EXISTS = (409, "EMAIL_ALREADY_EXISTS", "An account with this email already exists.", {"email": "Email is already registered."})
KAFKA_DOWN = (503, "SERVICE_UNAVAILABLE", "Event broker unavailable. Please try again.")
AUTH = [UNAUTHORIZED, TOKEN_EXPIRED]


def errors(*specs) -> dict[int, dict[str, Any]]:
    """errors((404, "GUEST_NOT_FOUND", "Guest not found."), ...) -> FastAPI `responses=` dict."""
    out: dict[int, dict[str, Any]] = {}
    for spec in specs:
        status, code, message, *rest = spec
        fields = rest[0] if rest else None
        entry = out.setdefault(status, {"model": ErrorResponse, "description": _DESCRIPTIONS.get(status, "Error"),
                                        "content": {"application/json": {"examples": {}}}})
        entry["content"]["application/json"]["examples"][code] = {
            "summary": code,
            "value": {"error": {"code": code, "message": message, "fields": fields}, "meta": _META},
        }
    return out


def ok_doc(model, description: str = "Success", status: int = 200) -> dict[int, dict[str, Any]]:
    return {status: {"model": model, "description": description}}
