"""Standard Kafka event envelope used by every Group 1 service.

Validate before publishing (EventEnvelope / new_event) and after consuming
(decode_event). Unknown fields are rejected so contract drift is caught early.
"""
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# e.g. "booking.requested", "debate.round.0"
EVENT_TYPE_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$"


class EnvelopeValidationError(ValueError):
    """Raised when a message does not match the event envelope contract."""


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    entity_type: str = Field(min_length=1, max_length=64, examples=["booking"])
    entity_id: str = Field(min_length=1, max_length=128, examples=["bk_123"])


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_type: str = Field(pattern=EVENT_TYPE_PATTERN, max_length=128)
    trace_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    actor_id: str = Field(min_length=1, max_length=128)
    entity: Entity
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)

    @field_validator("timestamp")
    @classmethod
    def _timezone_aware_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware (ISO 8601 with offset, UTC preferred)")
        return v.astimezone(timezone.utc)


def new_event(
    event_type: str,
    *,
    actor_id: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
    idempotency_key: str | None = None,
) -> EventEnvelope:
    """Build and validate an envelope.

    Pass the incoming request's trace_id to keep traces connected. Pass a
    deterministic idempotency_key (e.g. f"booking.approved:{booking_id}") when
    the same business action could be published twice.
    """
    return EventEnvelope(
        event_type=event_type,
        trace_id=trace_id or str(uuid4()),
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id,
        entity=Entity(entity_type=entity_type, entity_id=entity_id),
        payload=payload or {},
        idempotency_key=idempotency_key or f"{event_type}:{entity_type}:{entity_id}:{uuid4()}",
    )


def encode_event(envelope: EventEnvelope | dict[str, Any]) -> bytes:
    """Validate (if needed) and serialize an envelope to UTF-8 JSON bytes."""
    try:
        env = envelope if isinstance(envelope, EventEnvelope) else EventEnvelope.model_validate(envelope)
    except ValidationError as exc:
        raise EnvelopeValidationError(str(exc)) from exc
    return env.model_dump_json().encode("utf-8")


def decode_event(raw: bytes | str) -> EventEnvelope:
    """Parse and validate a consumed message. Raises EnvelopeValidationError."""
    try:
        return EventEnvelope.model_validate_json(raw)
    except ValidationError as exc:
        raise EnvelopeValidationError(str(exc)) from exc
