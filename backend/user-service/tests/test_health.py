from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_service_metadata():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "user-service"
    assert body["owner"] == "Nathan Pak"


def test_health_reports_application_only():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["dependencies"] == "not_checked"


def test_swagger_docs_available():
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "User & Host Service"


def test_cors_allows_frontend_origin():
    r = client.get("/health", headers={"Origin": "http://localhost:5101"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5101"
