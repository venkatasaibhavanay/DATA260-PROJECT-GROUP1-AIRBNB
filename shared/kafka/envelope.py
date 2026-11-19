"""Standard Kafka event envelope used by every Group 1 service (API doc section 3.1).

Validate before publishing (EventEnvelope / new_event) and after consuming
(decode_event). Unknown fields are rejected so contract drift is caught early.

The envelope has exactly 10 fields:
    event_id, event_type, schema_version, trace_id, timestamp, source_service,
    actor_id, entity{entity_type, entity_id}, idempotency_key, payload
"""
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# e.g. "booking.requested", "debate.round.0"
EVENT_TYPE_PATTERN = r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$"
# e.g. "guest:1001", "service:booking-worker"
ACTOR_ID_PATTERN = r"^(guest|host|admin|service|system):[A-Za-z0-9_-]+$"

EntityType = Literal[
    "guest", "host", "property", "availability", "reservation",
    "thread", "message", "review", "ai_task",
]


class EnvelopeValidationError(ValueError):
    """Raised when a message does not match the event envelope contract."""


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    entity_type: EntityType = Field(examples=["reservation"])
    entity_id: str = Field(min_length=1, max_length=128, examples=["9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d"])


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_id: str = Field(examples=["c1d2e3f4-5a6b-4c7d-8e9f-0a1b2c3d4e5f"])
    event_type: str = Field(pattern=EVENT_TYPE_PATTERN, max_length=128)
    schema_version: int = Field(ge=1)
    trace_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    source_service: str = Field(min_length=1, max_length=64, examples=["booking-service"])
    actor_id: str = Field(pattern=ACTOR_ID_PATTERN, max_length=128, examples=["guest:1001"])
    entity: Entity
    idempotency_key: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id")
    @classmethod
    def _uuid4(cls, v: str) -> str:
        try:
            parsed = UUID(v)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("event_id must be a UUID4 string") from exc
        if parsed.version != 4:
            raise ValueError("event_id must be a UUID4 string")
        return str(parsed)

    @field_validator("timestamp")
    @classmethod
    def _timezone_aware_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware (ISO 8601 with offset, UTC preferred)")
        return v.astimezone(timezone.utc)


def new_event(
    event_type: str,
    *,
    source_service: str,
    actor_id: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
    idempotency_key: str | None = None,
    schema_version: int = 1,
) -> EventEnvelope:
    """Build and validate an envelope. event_id and timestamp are generated.

    Pass the incoming request's trace_id to keep traces connected. The default
    idempotency_key is deterministic: f"{event_type}:{entity_id}". Pass your own
    (e.g. f"{event_type}:{entity_id}:{version}") when one entity can legitimately
    emit the same event type more than once.
    """
    try:
        return EventEnvelope(
            event_id=str(uuid4()),
            event_type=event_type,
            schema_version=schema_version,
            trace_id=trace_id or str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            source_service=source_service,
            actor_id=actor_id,
            entity=Entity(entity_type=entity_type, entity_id=entity_id),
            idempotency_key=idempotency_key or f"{event_type}:{entity_id}",
            payload=payload or {},
        )
    except ValidationError as exc:
        raise EnvelopeValidationError(str(exc)) from exc


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
