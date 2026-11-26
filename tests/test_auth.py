"""Tests for shared.auth (JWT HS256, role checks)."""
import jwt as pyjwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import shared.auth.jwt_auth as jwt_auth
from shared.auth import (
    CurrentUser,
    create_access_token,
    decode_access_token,
    get_current_user,
    optional_user,
    require_role,
    ws_user_from_token,
)
from shared.errors import AppError, register_exception_handlers

SECRET = "test-secret-please-change-0123456789"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("JWT_EXPIRY_MINUTES", "30")
    jwt_auth._settings.cache_clear()
    monkeypatch.setattr(jwt_auth, "is_revoked", lambda jti: False)  # no Redis in unit tests
    yield
    jwt_auth._settings.cache_clear()


@pytest.fixture
def client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/me")
    def me(user: CurrentUser = Depends(get_current_user)):
        return {"actor_id": user.actor_id}

    @app.get("/host-only")
    def host_only(user: CurrentUser = Depends(require_role("host"))):
        return {"ok": True}

    @app.get("/maybe")
    def maybe(user=Depends(optional_user)):
        return {"user": user.actor_id if user else None}

    return TestClient(app)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_decode_round_trip():
    user = decode_access_token(create_access_token(1001, "guest"))
    assert user.user_id == "1001" and user.role == "guest" and user.actor_id == "guest:1001"
    claims = pyjwt.decode(create_access_token(5, "host"), SECRET, algorithms=["HS256"])
    assert set(claims) == {"sub", "role", "user_id", "jti", "iat", "exp"}
    assert claims["exp"] - claims["iat"] == 30 * 60


def test_invalid_role_rejected_at_creation():
    with pytest.raises(ValueError):
        create_access_token(1, "superuser")


def test_expired_token_gives_401(client):
    token = create_access_token(1, "guest", expires_minutes=-1)
    r = client.get("/me", headers=auth(token))
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_bad_signature_gives_401(client):
    token = pyjwt.encode({"sub": "guest:1", "role": "guest", "user_id": "1", "jti": "j",
                          "iat": 0, "exp": 9999999999}, "wrong-secret-wrong-secret-wrong!!", algorithm="HS256")
    r = client.get("/me", headers=auth(token))
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"
    assert r.json()["error"]["message"] == "Missing or invalid token."


def test_missing_header_gives_401(client):
    r = client.get("/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"


def test_wrong_role_gives_403(client):
    r = client.get("/host-only", headers=auth(create_access_token(1, "guest")))
    assert r.status_code == 403
    assert r.json()["error"] == {"code": "ROLE_FORBIDDEN",
                                 "message": "This action is not allowed for your role.", "fields": None}


def test_right_role_passes(client):
    assert client.get("/host-only", headers=auth(create_access_token(2, "host"))).status_code == 200
    assert client.get("/me", headers=auth(create_access_token(2, "host"))).json() == {"actor_id": "host:2"}


def test_optional_user(client):
    assert client.get("/maybe").json() == {"user": None}
    assert client.get("/maybe", headers=auth(create_access_token(3, "guest"))).json() == {"user": "guest:3"}


def test_revoked_token_gives_401(client, monkeypatch):
    monkeypatch.setattr(jwt_auth, "is_revoked", lambda jti: True)
    r = client.get("/me", headers=auth(create_access_token(1, "guest")))
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"


def test_denylist_skipped_when_redis_down(monkeypatch):
    monkeypatch.undo()  # restore real is_revoked
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
    monkeypatch.setenv("REDIS_PORT", "1")  # nothing listens here
    jwt_auth._settings.cache_clear()
    assert jwt_auth.is_revoked("some-jti") is False


def test_ws_user_from_token():
    assert ws_user_from_token(create_access_token(9, "guest")).actor_id == "guest:9"
    with pytest.raises(AppError) as exc:
        ws_user_from_token(None)
    assert exc.value.status_code == 401
