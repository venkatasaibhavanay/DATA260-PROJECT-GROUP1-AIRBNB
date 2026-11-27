from fastapi.testclient import TestClient

import app.routes.messaging as messaging_route
from app.main import app
from shared.auth import create_access_token


client = TestClient(app)


def test_open_thread_requires_authentication():
    response = client.post(
        "/api/v1/threads/open",
        json={"property_id": 2001},
    )

    assert response.status_code == 401


def test_guest_can_open_thread(monkeypatch):
    fake_thread = {
        "thread_id": "thread-test-123",
        "property_id": 2001,
        "guest_id": 1001,
        "host_id": 501,
        "reservation_id": None,
        "created_datetime": "2026-11-02T18:40:00Z",
        "last_message_at": None,
        "unread_count": 0,
    }

    monkeypatch.setattr(
        messaging_route,
        "open_or_reuse_thread",
        lambda payload, user, authorization: (fake_thread, True),
    )

    token = create_access_token(1001, "guest")

    response = client.post(
        "/api/v1/threads/open",
        json={"property_id": 2001},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["thread_id"] == "thread-test-123"


def test_guest_reuses_existing_thread(monkeypatch):
    fake_thread = {
        "thread_id": "existing-thread-123",
        "property_id": 2001,
        "guest_id": 1001,
        "host_id": 501,
        "reservation_id": None,
        "created_datetime": "2026-11-02T18:40:00Z",
        "last_message_at": None,
        "unread_count": 0,
    }

    monkeypatch.setattr(
        messaging_route,
        "open_or_reuse_thread",
        lambda payload, user, authorization: (fake_thread, False),
    )

    token = create_access_token(1001, "guest")

    response = client.post(
        "/api/v1/threads/open",
        json={"property_id": 2001},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["thread_id"] == "existing-thread-123"


def test_host_can_open_thread(monkeypatch):
    fake_thread = {
        "thread_id": "host-thread-123",
        "property_id": 2001,
        "guest_id": 1001,
        "host_id": 501,
        "reservation_id": "9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d",
        "created_datetime": "2026-11-02T18:40:00Z",
        "last_message_at": None,
        "unread_count": 0,
    }

    monkeypatch.setattr(
        messaging_route,
        "open_or_reuse_thread",
        lambda payload, user, authorization: (fake_thread, True),
    )

    token = create_access_token(501, "host")

    response = client.post(
        "/api/v1/threads/open",
        json={
            "property_id": 2001,
            "guest_id": 1001,
            "reservation_id": "9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["host_id"] == 501


def test_host_request_requires_guest_and_reservation():
    token = create_access_token(501, "host")

    response = client.post(
        "/api/v1/threads/open",
        json={"property_id": 2001},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422