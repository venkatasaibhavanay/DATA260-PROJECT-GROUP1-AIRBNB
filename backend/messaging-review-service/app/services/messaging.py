from datetime import date, datetime, timezone
from os import getenv
from uuid import uuid4

import httpx

from app.database.connection import get_mongo_db
from app.schemas.messaging import (
    CreateReviewRequest,
    GetThreadRequest,
    ListMessagesRequest,
    MarkMessagesReadRequest,
    OpenThreadRequest,
    SendMessageRequest,
    ThreadsByUserRequest,
)
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

def get_thread_data(
    payload: GetThreadRequest,
    user: CurrentUser,
) -> dict:
    db = get_mongo_db()
    threads = db["threads"]

    thread = threads.find_one({"thread_id": payload.thread_id})

    if thread is None:
        raise AppError(
            404,
            "THREAD_NOT_FOUND",
            "The requested thread was not found.",
        )

    user_id = int(user.user_id)

    is_participant = (
        user.role == "guest" and thread.get("guest_id") == user_id
    ) or (
        user.role == "host" and thread.get("host_id") == user_id
    )

    if not is_participant:
        raise AppError(
            403,
            "NOT_THREAD_PARTICIPANT",
            "You are not a participant in this thread.",
        )

    thread.pop("_id", None)

    return {
        "thread_id": thread["thread_id"],
        "property": {
            "property_id": thread["property_id"],
            "title": thread.get("property_title", ""),
        },
        "guest": {
            "guest_id": thread["guest_id"],
            "name": thread.get("guest_name", ""),
        },
        "host": {
            "host_id": thread["host_id"],
            "name": thread.get("host_name", ""),
        },
        "reservation_id": thread.get("reservation_id"),
        "created_datetime": thread["created_datetime"],
        "last_message_at": thread.get("last_message_at"),
        "unread_count": thread.get("unread_count", 0),
    }

def list_threads_by_user(
    payload: ThreadsByUserRequest,
    user: CurrentUser,
) -> dict:
    db = get_mongo_db()
    threads = db["threads"]

    user_id = int(user.user_id)

    if user.role == "guest":
        query = {"guest_id": user_id}
    else:
        query = {"host_id": user_id}

    if payload.unread_only:
        query["unread_count"] = {"$gt": 0}

    total = threads.count_documents(query)
    skip = (payload.page - 1) * payload.page_size

    documents = (
        threads.find(query, {"_id": 0})
        .sort("last_message_at", -1)
        .skip(skip)
        .limit(payload.page_size)
    )

    items = []

    for thread in documents:
        if user.role == "guest":
            other_party = {
                "actor_id": f"host:{thread['host_id']}",
                "name": thread.get("host_name", ""),
            }
        else:
            other_party = {
                "actor_id": f"guest:{thread['guest_id']}",
                "name": thread.get("guest_name", ""),
            }

        items.append(
            {
                "thread_id": thread["thread_id"],
                "property_title": thread.get("property_title", ""),
                "other_party": other_party,
                "last_message_preview": thread.get(
                    "last_message_preview", ""
                ),
                "last_message_at": thread.get("last_message_at"),
                "unread_count": thread.get("unread_count", 0),
            }
        )

    total_pages = (
        (total + payload.page_size - 1) // payload.page_size
        if total
        else 0
    )

    return {
        "items": items,
        "page": payload.page,
        "page_size": payload.page_size,
        "total": total,
        "total_pages": total_pages,
    }

def list_messages(
    payload: ListMessagesRequest,
    user: CurrentUser,
) -> dict:
    db = get_mongo_db()
    threads = db["threads"]
    messages = db["messages"]

    thread = threads.find_one(
        {"thread_id": payload.thread_id}
    )

    if thread is None:
        raise AppError(
            404,
            "THREAD_NOT_FOUND",
            "The requested thread was not found.",
        )

    user_id = int(user.user_id)

    is_participant = (
        user.role == "guest" and thread.get("guest_id") == user_id
    ) or (
        user.role == "host" and thread.get("host_id") == user_id
    )

    if not is_participant:
        raise AppError(
            403,
            "NOT_THREAD_PARTICIPANT",
            "You are not a participant in this thread.",
        )

    query = {"thread_id": payload.thread_id}

    if payload.before is not None:
        query["timestamp"] = {"$lt": payload.before}

    records = list(
        messages.find(query, {"_id": 0})
        .sort("timestamp", -1)
        .limit(payload.limit + 1)
    )

    has_more = len(records) > payload.limit
    records = records[:payload.limit]

    next_before = None
    if records:
        next_before = records[-1].get("timestamp")

    return {
        "items": records,
        "next_before": next_before,
        "has_more": has_more,
    }

def send_message(
    payload: SendMessageRequest,
    user: CurrentUser,
    idempotency_key: str,
) -> tuple[dict, bool]:
    if not payload.message_text.strip():
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "message_text cannot be empty.",
        )

    db = get_mongo_db()
    threads = db["threads"]
    messages = db["messages"]

    thread = threads.find_one(
        {"thread_id": payload.thread_id}
    )

    if thread is None:
        raise AppError(
            404,
            "THREAD_NOT_FOUND",
            "The requested thread was not found.",
        )

    user_id = int(user.user_id)

    is_participant = (
        user.role == "guest" and thread.get("guest_id") == user_id
    ) or (
        user.role == "host" and thread.get("host_id") == user_id
    )

    if not is_participant:
        raise AppError(
            403,
            "NOT_THREAD_PARTICIPANT",
            "You are not a participant in this thread.",
        )

    existing = messages.find_one(
        {
            "thread_id": payload.thread_id,
            "sender_id": user.actor_id,
            "idempotency_key": idempotency_key,
        },
        {"_id": 0},
    )

    if existing is not None:
        return existing, False

    if user.role == "guest":
        receiver_id = f"host:{thread['host_id']}"
    else:
        receiver_id = f"guest:{thread['guest_id']}"

    message = {
        "message_id": uuid4().hex,
        "thread_id": payload.thread_id,
        "sender_id": user.actor_id,
        "receiver_id": receiver_id,
        "timestamp": datetime.now(timezone.utc),
        "message_text": payload.message_text,
        "delivery_status": "sent",
        "idempotency_key": idempotency_key,
    }

    messages.insert_one(message.copy())

    return message, True

def mark_messages_read(
    payload: MarkMessagesReadRequest,
    user: CurrentUser,
) -> dict:
    db = get_mongo_db()
    threads = db["threads"]
    messages = db["messages"]

    thread = threads.find_one(
        {"thread_id": payload.thread_id}
    )

    if thread is None:
        raise AppError(
            404,
            "THREAD_NOT_FOUND",
            "The requested thread was not found.",
        )

    user_id = int(user.user_id)

    is_participant = (
        user.role == "guest" and thread.get("guest_id") == user_id
    ) or (
        user.role == "host" and thread.get("host_id") == user_id
    )

    if not is_participant:
        raise AppError(
            403,
            "NOT_THREAD_PARTICIPANT",
            "You are not a participant in this thread.",
        )

    received_messages = list(
        messages.find(
            {
                "thread_id": payload.thread_id,
                "receiver_id": user.actor_id,
                "delivery_status": {
                    "$in": ["sent", "delivered"]
                },
            },
            {"_id": 0},
        ).sort("timestamp", 1)
    )

    message_ids = []
    found_target = False

    for message in received_messages:
        message_ids.append(message["message_id"])

        if message["message_id"] == payload.up_to_message_id:
            found_target = True
            break

    if not found_target:
        raise AppError(
            404,
            "MESSAGE_NOT_FOUND",
            "The requested message was not found.",
        )

    result = messages.update_many(
        {
            "message_id": {"$in": message_ids},
            "receiver_id": user.actor_id,
            "delivery_status": {
                "$in": ["sent", "delivered"]
            },
        },
        {"$set": {"delivery_status": "read"}},
    )

    unread_count = messages.count_documents(
        {
            "thread_id": payload.thread_id,
            "receiver_id": user.actor_id,
            "delivery_status": {
                "$in": ["sent", "delivered"]
            },
        }
    )

    threads.update_one(
        {"thread_id": payload.thread_id},
        {"$set": {"unread_count": unread_count}},
    )

    return {
        "thread_id": payload.thread_id,
        "updated_count": result.modified_count,
        "unread_count": unread_count,
    }

def create_review(
    payload: CreateReviewRequest,
    user: CurrentUser,
) -> dict:
    db = get_mongo_db()
    eligibility = db["review_eligibility"]
    reviews = db["reviews"]

    guest_id = int(user.user_id)
    reservation_id = str(payload.reservation_id)

    eligible_stay = eligibility.find_one(
        {
            "reservation_id": reservation_id,
            "guest_id": guest_id,
        },
        {"_id": 0},
    )

    if eligible_stay is None:
        raise AppError(
            403,
            "NOT_RESERVATION_GUEST",
            "You are not the guest for this reservation.",
        )

    check_out = eligible_stay.get("check_out")

    if check_out is not None:
        if isinstance(check_out, datetime):
            check_out_date = check_out.date()
        else:
            check_out_date = date.fromisoformat(
                str(check_out)[:10]
            )

        if check_out_date > datetime.now(timezone.utc).date():
            raise AppError(
                422,
                "STAY_NOT_COMPLETED",
                "The stay is not completed yet.",
            )

    existing = reviews.find_one(
        {"reservation_id": reservation_id},
        {"_id": 0},
    )

    if existing is not None:
        raise AppError(
            409,
            "ALREADY_REVIEWED",
            "This reservation has already been reviewed.",
        )

    review = {
        "review_id": uuid4().hex,
        "reservation_id": reservation_id,
        "property_id": eligible_stay["property_id"],
        "guest_id": guest_id,
        "host_id": eligible_stay["host_id"],
        "rating": payload.rating,
        "review_text": payload.review_text,
        "created_datetime": datetime.now(timezone.utc),
        "response_text": None,
        "responded_datetime": None,
    }

    reviews.insert_one(review.copy())

    return review