"""Positive and negative tests for the shared Kafka event envelope."""
import json
from datetime import datetime

import pytest

from shared.kafka import (
    EnvelopeValidationError,
    EventEnvelope,
    decode_event,
    encode_event,
    new_event,
)
from shared.kafka.consumer import handle_message


def valid_dict(**overrides):
    d = {
        "event_type": "booking.requested",
        "trace_id": "trace-123",
        "timestamp": "2026-11-11T21:05:00Z",
        "actor_id": "user_42",
        "entity": {"entity_type": "booking", "entity_id": "bk_1001"},
        "payload": {"property_id": "prop_7"},
        "idempotency_key": "booking.requested:bk_1001",
    }
    d.update(overrides)
    return d


# ---------- positive ----------

def test_new_event_builds_valid_envelope():
    env = new_event("booking.approved", actor_id="host_1", entity_type="booking", entity_id="bk_1")
    assert env.timestamp.tzinfo is not None
    assert env.trace_id and env.idempotency_key
    assert env.entity.entity_id == "bk_1"


def test_round_trip_encode_decode():
    env = EventEnvelope.model_validate(valid_dict())
    decoded = decode_event(encode_event(env))
    assert decoded == env


def test_timestamp_normalised_to_utc():
    env = EventEnvelope.model_validate(valid_dict(timestamp="2026-11-11T13:05:00-08:00"))
    assert env.timestamp.utcoffset().total_seconds() == 0
    assert env.timestamp.hour == 21


@pytest.mark.parametrize("event_type", ["debate.round.0", "ai.results", "review.created"])
def test_known_event_type_shapes_accepted(event_type):
    EventEnvelope.model_validate(valid_dict(event_type=event_type))


# ---------- negative ----------

@pytest.mark.parametrize("missing", [
    "event_type", "trace_id", "timestamp", "actor_id", "entity", "idempotency_key",
])
def test_missing_required_field_rejected(missing):
    d = valid_dict()
    d.pop(missing)
    with pytest.raises(EnvelopeValidationError):
        encode_event(d)


def test_naive_timestamp_rejected():
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(timestamp=datetime(2026, 11, 11, 12, 0).isoformat()))


@pytest.mark.parametrize("bad", ["Booking.Requested", "booking", "booking..x", "booking requested"])
def test_bad_event_type_rejected(bad):
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(event_type=bad))


def test_entity_requires_type_and_id():
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(entity={"entity_type": "booking"}))
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(entity={"entity_type": "", "entity_id": "x"}))


def test_unknown_top_level_field_rejected():
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(extra_field="nope"))


def test_decode_rejects_malformed_json():
    with pytest.raises(EnvelopeValidationError):
        decode_event(b"{not json")


# ---------- consumer + DLQ ----------

def test_handle_message_dispatches_valid_event():
    seen = []
    ok = handle_message("booking.requested", json.dumps(valid_dict()).encode(), seen.append)
    assert ok and seen[0].entity.entity_id == "bk_1001"


def test_handle_message_routes_invalid_to_dlq():
    dlq = []
    ok = handle_message("booking.requested", b'{"event_type": "x"}', lambda e: None,
                        send_to_dlq=lambda topic, value, headers: dlq.append(topic))
    assert ok is False
    assert dlq == ["booking.requested.dlq"]
