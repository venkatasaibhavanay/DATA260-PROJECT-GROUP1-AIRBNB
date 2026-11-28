"""Event handlers for the user-counters and user-host-metrics consumer groups.

Each handler runs in ONE database transaction that also records
(consumer_group, idempotency_key) in user_processed_events, so a redelivered
event is applied exactly once (API doc 3.3).
"""
import logging
import statistics
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.repositories import users as repo
from shared.kafka.consumer import PermanentError, TransientError
from shared.kafka.envelope import EventEnvelope
from shared.kafka.idempotency import mysql_already_processed, mysql_mark_processed
from shared.kafka.topics import BOOKING_APPROVED, MESSAGE_SENT, PROPERTY_SAVED, PROPERTY_UNSAVED

logger = logging.getLogger("user_service.workers")

PROCESSED_TABLE = "user_processed_events"
COUNTERS_GROUP = "user-counters"
HOST_METRICS_GROUP = "user-host-metrics"
COUNTERS_TOPICS = [PROPERTY_SAVED, PROPERTY_UNSAVED, BOOKING_APPROVED]
HOST_METRICS_TOPICS = [MESSAGE_SENT]
REPLY_WINDOW = timedelta(hours=24)


def _int_id(value, prefix: Optional[str] = None) -> int:
    """Accept 1001, "1001" or "guest:1001"."""
    if isinstance(value, str) and ":" in value:
        role, _, value = value.partition(":")
        if prefix and role != prefix:
            raise PermanentError(f"expected a {prefix} id, got {role}")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise PermanentError(f"invalid id: {value!r}") from None


def _role_of(value) -> Optional[str]:
    return value.partition(":")[0] if isinstance(value, str) and ":" in value else None


def _ts(value) -> datetime:
    """ISO 8601 string -> naive UTC."""
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            raise PermanentError(f"invalid timestamp: {value!r}") from None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _require(payload: dict, *names: str) -> None:
    missing = [n for n in names if payload.get(n) is None]
    if missing:
        raise PermanentError(f"payload missing {', '.join(missing)}")


def run_once(factory: sessionmaker, group: str, event: EventEnvelope, apply: Callable[[Session, EventEnvelope], None]) -> bool:
    """Apply an event exactly once. Returns False if it was a duplicate."""
    try:
        with factory() as db, db.begin():
            conn = db.connection()
            if mysql_already_processed(conn, PROCESSED_TABLE, group, event.idempotency_key):
                logger.info("duplicate_event_skipped group=%s key=%s", group, event.idempotency_key)
                return False
            apply(db, event)
            mysql_mark_processed(conn, PROCESSED_TABLE, group, event.idempotency_key)
            return True
    except IntegrityError:
        # another consumer instance recorded the same key first: treat as duplicate
        logger.info("duplicate_event_race group=%s key=%s", group, event.idempotency_key)
        return False
    except OperationalError as exc:  # DB down, timeout, deadlock -> retry 1 s, 2 s, 4 s
        raise TransientError(str(exc)) from exc
    except DBAPIError as exc:
        raise PermanentError(str(exc)) from exc


# ---------- user-counters ----------

def apply_counters(db: Session, event: EventEnvelope) -> None:
    p = event.payload
    _require(p, "guest_id")
    guest_id = _int_id(p["guest_id"], "guest")
    if event.event_type == PROPERTY_SAVED:
        column, delta = "saved_properties_count", 1
    elif event.event_type == PROPERTY_UNSAVED:
        column, delta = "saved_properties_count", -1
    elif event.event_type == BOOKING_APPROVED:
        column, delta = "booking_count", 1
    else:
        raise PermanentError(f"unexpected event_type {event.event_type}")
    if repo.adjust_guest_counter(db, guest_id, column, delta) == 0:
        logger.warning("counter_skipped_unknown_guest guest_id=%s event=%s", guest_id, event.event_type)


# ---------- user-host-metrics ----------

def recompute_host_metrics(db: Session, host_id: int) -> None:
    host = repo.get_host(db, host_id)
    if host is None:
        return
    rows = repo.recent_thread_responses(db, host_id)
    if not rows:
        return
    answered = [r for r in rows if r.host_first_reply_at is not None
                and r.host_first_reply_at - r.guest_first_message_at <= REPLY_WINDOW]
    host.response_rate = (Decimal(len(answered)) / Decimal(len(rows))).quantize(Decimal("0.01"))
    minutes = [(r.host_first_reply_at - r.guest_first_message_at).total_seconds() / 60
               for r in rows if r.host_first_reply_at is not None]
    host.response_time_minutes = round(statistics.median(minutes)) if minutes else None


def apply_host_metrics(db: Session, event: EventEnvelope) -> None:
    p = event.payload
    _require(p, "thread_id", "sender_id", "receiver_id", "timestamp")
    thread_id = str(p["thread_id"])
    sent_at = _ts(p["timestamp"])
    sender_role = _role_of(p["sender_id"])

    if p.get("is_first_guest_message"):
        host_id = _int_id(p["receiver_id"], "host")
        if repo.get_thread_response(db, thread_id) is None:
            repo.add_thread_response(db, thread_id, host_id, sent_at)
        recompute_host_metrics(db, host_id)
        return

    if p.get("reply_to_guest_message_at") is None or sender_role == "guest":
        return  # only host replies to a guest message affect the metrics
    host_id = _int_id(p["sender_id"], "host")
    row = repo.get_thread_response(db, thread_id)
    if row is None:
        # first guest message was never seen (e.g. sent before this consumer existed)
        repo.add_thread_response(db, thread_id, host_id, _ts(p["reply_to_guest_message_at"]))
        row = repo.get_thread_response(db, thread_id)
    if row.host_first_reply_at is None:
        row.host_first_reply_at = sent_at
    recompute_host_metrics(db, host_id)


def make_handler(factory: sessionmaker, group: str) -> Callable[[EventEnvelope], None]:
    apply = apply_counters if group == COUNTERS_GROUP else apply_host_metrics
    return lambda event: run_once(factory, group, event, apply)
