from datetime import datetime, timezone
from os import getenv
from uuid import uuid4

import httpx

from app.database.connection import get_mongo_db
from app.schemas.messaging import OpenThreadRequest
from app.services import messaging as messaging_service
from shared.auth import CurrentUser
from shared.errors import AppError

GATEWAY_URL = getenv(
    "GATEWAY_URL", "http://localhost:8000"
).rstrip("/")

def _call_service(url: str, body: dict, authorization: str | None) -> dict:
    headers = {}
    if authorization:
        headers["Authorization"] = authorization

    try:
        response = httpx.post(
            url,
            json=body,
            headers=headers,
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise AppError(
            503,
            "SERVICE_UNAVAILABLE",
            "A required service is unavailable.",
        ) from exc

    if response.status_code >= 400:
        if response.status_code == 404:
            raise AppError(404, "RESOURCE_NOT_FOUND", "The requested resource was not found.")
        raise AppError(
            503,
            "SERVICE_UNAVAILABLE",
            "A required service returned an error.",
        )

    return response.json().get("data", {})


def _get_property(property_id: int, authorization: str | None) -> dict:
    return _call_service(
        f"{GATEWAY_URL}/api/v1/properties/get",
        {"property_id": property_id},
        authorization,
    )


def _get_reservation(reservation_id: str, authorization: str | None) -> dict:
    return _call_service(
        f"{GATEWAY_URL}/api/v1/bookings/get",
        {"reservation_id": reservation_id},
        authorization,
    )


def open_or_reuse_thread(
    payload: OpenThreadRequest,
    user: CurrentUser,
    authorization: str | None,
) -> tuple[dict, bool]:

    if user.role == "guest":
        guest_id = int(user.user_id)
        property_data = _get_property(payload.property_id, authorization)

        host_data = property_data.get("host") or {}
        host_id = host_data.get("host_id")

        if host_id is None:
            raise AppError(
                404,
                "PROPERTY_NOT_FOUND",
                "The property host could not be found.",
            )

        reservation_id = None

    else:
        if payload.guest_id is None or payload.reservation_id is None:
            raise AppError(
                422,
                "VALIDATION_ERROR",
                "guest_id and reservation_id are required for hosts.",
            )

        guest_id = int(payload.guest_id)
        host_id = int(user.user_id)

        reservation = _get_reservation(
            str(payload.reservation_id),
            authorization,
        )

        if (
            reservation.get("property", {}).get("property_id")
            != payload.property_id
            or reservation.get("guest_id") != guest_id
            or reservation.get("host_id") != host_id
            or reservation.get("status") not in {"pending_host", "approved"}
        ):
            raise AppError(
                403,
                "THREAD_NOT_ALLOWED",
                "The host is not authorized to open this thread.",
            )

        reservation_id = str(payload.reservation_id)

        # guest/host validation logic comes first

    db = get_mongo_db()
    threads = db["threads"]

    threads.create_index(
        [("property_id", 1), ("guest_id", 1)],
        unique=True,
    )

    existing = threads.find_one(
        {
            "property_id": payload.property_id,
            "guest_id": guest_id,
        }
    )

    if existing:
        existing.pop("_id", None)
        return existing, False

    now = datetime.now(timezone.utc)
    thread = {
        "thread_id": uuid4().hex,
        "property_id": payload.property_id,
        "guest_id": guest_id,
        "host_id": host_id,
        "reservation_id": reservation_id,
        "created_datetime": now,
        "last_message_at": None,
        "unread_count": 0,
    }

    threads.insert_one(thread)
    thread.pop("_id", None)

    return thread, True

class FakeThreads:
    def __init__(self):
        self.documents = []

    def create_index(self, *args, **kwargs):
        return "property_guest_unique_index"

    def find_one(self, query):
        for document in self.documents:
            if (
                document["property_id"] == query["property_id"]
                and document["guest_id"] == query["guest_id"]
            ):
                return document.copy()
        return None

    def insert_one(self, document):
        self.documents.append(document.copy())


class FakeDatabase:
    def __init__(self):
        self.threads = FakeThreads()

    def __getitem__(self, name):
        assert name == "threads"
        return self.threads


def test_real_guest_service_uses_mocked_property_response(monkeypatch):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        messaging_service,
        "get_mongo_db",
        lambda: fake_database,
    )

    monkeypatch.setattr(
        messaging_service,
        "_get_property",
        lambda property_id, authorization: {
            "property_id": 2001,
            "title": "Sunny 2BR near Downtown San Jose",
            "host": {
                "host_id": 501,
                "name": "Daniel Ortiz",
                "verification_status": "verified",
            },
        },
    )

    user = CurrentUser(
        user_id="1001",
        role="guest",
        actor_id="guest:1001",
        jti="test-jti",
        exp=9999999999,
    )

    payload = OpenThreadRequest(property_id=2001)

    thread, created = messaging_service.open_or_reuse_thread(
        payload=payload,
        user=user,
        authorization="Bearer test-token",
    )

    assert created is True
    assert thread["property_id"] == 2001
    assert thread["guest_id"] == 1001
    assert thread["host_id"] == 501
    assert thread["reservation_id"] is None