"""Tests for the shared error shape and request-context headers."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field

from shared.errors import REQUEST_HEADER, TRACE_HEADER, AppError, register_exception_handlers
from shared.responses import Envelope, ok
from shared.schemas import StrictModel


class Body(StrictModel):
    name: str = Field(min_length=1)
    nights: int = Field(ge=1)


def make_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/v1/things/create", response_model=Envelope[dict])
    def create(body: Body, request: __import__("fastapi").Request):
        return ok({"name": body.name}, request)

    @app.post("/api/v1/things/fail")
    def fail():
        raise AppError(409, "DATES_UNAVAILABLE", "Dates are taken.", fields={"check_in": "taken"})

    @app.post("/api/v1/things/legacy")
    def legacy():
        raise AppError(400, "LEGACY", "Old style.", details={"a": 1})

    @app.get("/api/v1/things/boom")
    def boom():
        raise RuntimeError("secret internals")

    return app


client = TestClient(make_app(), raise_server_exceptions=False)


def assert_error_shape(r, status, code):
    assert r.status_code == status
    body = r.json()
    assert set(body) == {"error", "meta"}
    assert set(body["error"]) == {"code", "message", "fields"}
    assert body["error"]["code"] == code
    assert set(body["meta"]) == {"request_id", "trace_id"}
    assert r.headers[TRACE_HEADER] == body["meta"]["trace_id"]
    assert r.headers[REQUEST_HEADER] == body["meta"]["request_id"]
    return body


def test_unknown_route_404_shape_and_headers():
    body = assert_error_shape(client.get("/api/v1/nope"), 404, "NOT_FOUND")
    assert body["error"]["fields"] is None


def test_method_not_allowed_code():
    assert_error_shape(client.get("/api/v1/things/create"), 405, "METHOD_NOT_ALLOWED")


def test_validation_error_shape():
    r = client.post("/api/v1/things/create", json={"name": "", "nights": 0, "extra": 1})
    body = assert_error_shape(r, 422, "VALIDATION_ERROR")
    assert body["error"]["message"] == "One or more fields are invalid."
    assert set(body["error"]["fields"]) == {"name", "nights", "extra"}  # no leading "body"


def test_app_error_shape():
    body = assert_error_shape(client.post("/api/v1/things/fail"), 409, "DATES_UNAVAILABLE")
    assert body["error"]["fields"] == {"check_in": "taken"}


def test_app_error_details_alias():
    body = assert_error_shape(client.post("/api/v1/things/legacy"), 400, "LEGACY")
    assert body["error"]["fields"] == {"a": 1}


def test_unhandled_exception_is_500_without_stack_trace():
    r = client.get("/api/v1/things/boom")
    body = assert_error_shape(r, 500, "INTERNAL_ERROR")
    assert body["error"]["message"] == "Unexpected server error."
    assert "secret internals" not in r.text and "Traceback" not in r.text


def test_incoming_headers_are_echoed_case_insensitive():
    r = client.get("/api/v1/nope", headers={"x-trace-id": "trace-abc", "X-Request-ID": "req-1"})
    assert r.headers[TRACE_HEADER] == "trace-abc"
    assert r.json()["meta"] == {"request_id": "req-1", "trace_id": "trace-abc"}


def test_success_envelope_and_headers():
    r = client.post("/api/v1/things/create", json={"name": "a", "nights": 2},
                    headers={"X-Trace-ID": "t-9"})
    assert r.status_code == 200
    assert r.json()["data"] == {"name": "a"}
    assert r.json()["meta"]["trace_id"] == "t-9"
    assert r.headers[TRACE_HEADER] == "t-9" and r.headers[REQUEST_HEADER]


def test_health_is_unwrapped_but_has_headers():
    r = client.get("/health")
    assert r.json() == {"status": "ok"}
    assert r.headers[TRACE_HEADER] and r.headers[REQUEST_HEADER]
