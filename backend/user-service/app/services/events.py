"""Kafka publishing for user-service (user.registered, guest.deleted).

Events are published BEFORE the database commit: if Kafka is unavailable the
request fails with 503 SERVICE_UNAVAILABLE and nothing is saved (API doc 2.3).
"""
import logging
import threading
from typing import Any, Protocol

from fastapi import Request

from app.config import settings
from shared.errors import AppError
from shared.errors.errors import get_trace_id
from shared.kafka import EnvelopeValidationError, new_event
from shared.kafka.producer import EnvelopeProducer
from shared.kafka.topics import GUEST_DELETED, USER_REGISTERED

logger = logging.getLogger("user_service.events")
SOURCE_SERVICE = "user-service"


class Publisher(Protocol):
    def publish(self, topic: str, envelope: Any, key: str | None = None, timeout_s: float = 10) -> Any: ...


class _FastFailProducer(EnvelopeProducer):
    """EnvelopeProducer that fails within seconds (not 60 s) when the broker is down."""

    def __init__(self, bootstrap_servers: str, client_id: str):
        from kafka import KafkaProducer

        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers, client_id=client_id, acks="all", retries=3,
            max_block_ms=5000, request_timeout_ms=10000, api_version_auto_timeout_ms=3000,
        )


_lock = threading.Lock()
_producer: EnvelopeProducer | None = None


def get_publisher() -> Publisher:
    """FastAPI dependency. Tests override it with a fake."""
    return _KafkaPublisher()


class _KafkaPublisher:
    def publish(self, topic, envelope, key=None, timeout_s=10):
        global _producer
        try:
            with _lock:
                if _producer is None:
                    _producer = _FastFailProducer(settings.kafka_bootstrap_servers, "user-service")
            return _producer.publish(topic, envelope, key=key, timeout_s=timeout_s)
        except EnvelopeValidationError:
            raise AppError(500, "INTERNAL_ERROR", "Unexpected server error.") from None
        except Exception as exc:  # noqa: BLE001 - broker down, timeout, ...
            logger.warning("kafka_publish_failed topic=%s error=%s", topic, exc)
            with _lock:
                _producer = None
            raise AppError(503, "SERVICE_UNAVAILABLE", "Event broker unavailable. Please try again.") from None


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def publish_user_registered(pub: Publisher, request: Request, *, role: str, user_id: int,
                            created, location: str | None = None) -> None:
    payload = {"user_id": user_id, "role": role, "created_datetime": _iso(created)}
    if role == "guest":
        payload["location"] = location
    actor = f"{role}:{user_id}"
    env = new_event(USER_REGISTERED, source_service=SOURCE_SERVICE, actor_id=actor,
                    entity_type=role, entity_id=str(user_id), payload=payload,
                    trace_id=get_trace_id(request))
    pub.publish(USER_REGISTERED, env, key=actor)


def publish_guest_deleted(pub: Publisher, request: Request, *, guest_id: int, deleted) -> None:
    env = new_event(GUEST_DELETED, source_service=SOURCE_SERVICE, actor_id=f"guest:{guest_id}",
                    entity_type="guest", entity_id=str(guest_id),
                    payload={"guest_id": guest_id, "deleted_datetime": _iso(deleted)},
                    trace_id=get_trace_id(request))
    pub.publish(GUEST_DELETED, env, key=str(guest_id))
