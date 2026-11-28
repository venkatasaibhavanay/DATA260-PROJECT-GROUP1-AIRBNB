from fastapi.testclient import TestClient

import app.routes.messaging as messaging_route
from app.main import app
from shared.auth import create_access_token

import pytest
from starlette.websockets import WebSocketDisconnect

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

def test_participant_can_get_thread(monkeypatch):
    fake_thread = {
        "thread_id": "thread-test-123",
        "property": {
            "property_id": 2001,
            "title": "Sunny 2BR near Downtown San Jose",
        },
        "guest": {
            "guest_id": 1001,
            "name": "Maya C.",
        },
        "host": {
            "host_id": 501,
            "name": "Daniel Ortiz",
        },
        "reservation_id": None,
        "created_datetime": "2026-11-02T18:40:00Z",
        "last_message_at": None,
        "unread_count": 0,
    }

    monkeypatch.setattr(
        messaging_route,
        "get_thread_data",
        lambda payload, user: fake_thread,
    )

    token = create_access_token(1001, "guest")

    response = client.post(
        "/api/v1/threads/get",
        json={"thread_id": "thread-test-123"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["thread_id"] == "thread-test-123"
    assert response.json()["data"]["property"]["property_id"] == 2001

def test_guest_can_list_threads(monkeypatch):
    fake_threads = {
        "items": [
            {
                "thread_id": "thread-test-123",
                "property_title": "Sunny 2BR near Downtown San Jose",
                "other_party": {
                    "actor_id": "host:501",
                    "name": "Daniel Ortiz",
                },
                "last_message_preview": "Is parking included?",
                "last_message_at": None,
                "unread_count": 1,
            }
        ],
        "page": 1,
        "page_size": 20,
        "total": 1,
        "total_pages": 1,
    }

    monkeypatch.setattr(
        messaging_route,
        "list_threads_by_user",
        lambda payload, user: fake_threads,
    )

    token = create_access_token(1001, "guest")

    response = client.post(
        "/api/v1/threads/byUser",
        json={
            "unread_only": False,
            "page": 1,
            "page_size": 20,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["items"][0]["thread_id"] == "thread-test-123"

def test_participant_can_list_messages(monkeypatch):
    fake_messages = {
        "items": [
            {
                "message_id": "message-test-123",
                "thread_id": "thread-test-123",
                "sender_id": "guest:1001",
                "receiver_id": "host:501",
                "timestamp": "2026-11-02T18:40:30Z",
                "message_text": "Is parking included?",
                "delivery_status": "read",
            }
        ],
        "next_before": None,
        "has_more": False,
    }

    monkeypatch.setattr(
        messaging_route,
        "list_messages",
        lambda payload, user: fake_messages,
    )

    token = create_access_token(1001, "guest")

    response = client.post(
        "/api/v1/messages/list",
        json={
            "thread_id": "thread-test-123",
            "limit": 50,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["has_more"] is False
    assert response.json()["data"]["items"][0]["message_id"] == (
        "message-test-123"
    )

def test_participant_can_send_message(monkeypatch):
    fake_message = {
        "message_id": "message-test-123",
        "thread_id": "thread-test-123",
        "sender_id": "guest:1001",
        "receiver_id": "host:501",
        "timestamp": "2026-11-02T18:40:30Z",
        "message_text": "Is parking included?",
        "delivery_status": "sent",
    }

    monkeypatch.setattr(
        messaging_route,
        "send_message",
        lambda payload, user, idempotency_key: (
            fake_message,
            True,
        ),
    )

    token = create_access_token(1001, "guest")

    response = client.post(
        "/api/v1/messages/send",
        json={
            "thread_id": "thread-test-123",
            "message_text": "Is parking included?",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "test-idempotency-key-123",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["message_id"] == "message-test-123"
    assert response.json()["data"]["delivery_status"] == "sent"

def test_participant_can_mark_messages_read(monkeypatch):
    fake_result = {
        "thread_id": "thread-test-123",
        "updated_count": 1,
        "unread_count": 0,
    }

    monkeypatch.setattr(
        messaging_route,
        "mark_messages_read",
        lambda payload, user: fake_result,
    )

    token = create_access_token(1001, "guest")

    response = client.post(
        "/api/v1/messages/markRead",
        json={
            "thread_id": "thread-test-123",
            "up_to_message_id": "message-test-123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["updated_count"] == 1
    assert response.json()["data"]["unread_count"] == 0

def test_websocket_rejects_invalid_token():
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(
            "/api/v1/ws/messages?token=invalid-token"
        ):
            pass

    assert error.value.code == 4401

def test_guest_can_create_review(monkeypatch):
    fake_review = {
        "review_id": "review-test-123",
        "reservation_id": "9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d",
        "property_id": 2001,
        "guest_id": 1001,
        "host_id": 501,
        "rating": 5,
        "review_text": "Clean, quiet, and very comfortable stay.",
        "created_datetime": "2026-12-21T10:00:00Z",
        "response_text": None,
    }

    monkeypatch.setattr(
        messaging_route,
        "create_review",
        lambda payload, user: fake_review,
    )

    token = create_access_token(1001, "guest")

    response = client.post(
        "/api/v1/reviews/create",
        json={
            "reservation_id": "9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d",
            "rating": 5,
            "review_text": "Clean, quiet, and very comfortable stay.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["review_id"] == "review-test-123"
    assert response.json()["data"]["rating"] == 5