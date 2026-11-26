"""Positive and negative tests for the shared Kafka event envelope, producer and DLQ."""
import json
import logging
import sys
import types
from datetime import datetime
from uuid import UUID

import pytest

from shared.kafka import (
    EnvelopeValidationError,
    EventEnvelope,
    decode_event,
    encode_event,
    new_event,
)
from shared.kafka.consumer import (
    DLQ_KEYS,
    PermanentError,
    TransientError,
    build_dlq_record,
    handle_message,
    process_message,
)

ENVELOPE_FIELDS = [
    "event_id", "event_type", "schema_version", "trace_id", "timestamp",
    "source_service", "actor_id", "entity", "idempotency_key", "payload",
]


def valid_dict(**overrides):
    d = {
        "event_id": "c1d2e3f4-5a6b-4c7d-8e9f-0a1b2c3d4e5f",
        "event_type": "booking.requested",
        "schema_version": 1,
        "trace_id": "7f3c9a2e-1b4d-4e8a-9c6f-2d5b8e1a0c47",
        "timestamp": "2026-11-11T21:05:00Z",
        "source_service": "booking-service",
        "actor_id": "guest:42",
        "entity": {"entity_type": "reservation", "entity_id": "9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d"},
        "idempotency_key": "booking.requested:9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d",
        "payload": {"property_id": 2001},
    }
    d.update(overrides)
    return d


def raw(**overrides) -> bytes:
    return json.dumps(valid_dict(**overrides)).encode()


# ---------- positive ----------

def test_envelope_has_exactly_ten_fields():
    assert list(EventEnvelope.model_fields) == ENVELOPE_FIELDS


def test_new_event_builds_valid_envelope():
    env = new_event("booking.approved", source_service="booking-service", actor_id="host:1",
                    entity_type="reservation", entity_id="r1")
    assert UUID(env.event_id).version == 4
    assert env.schema_version == 1
    assert env.timestamp.tzinfo is not None
    assert env.trace_id
    assert env.idempotency_key == "booking.approved:r1"  # deterministic default
    assert env.source_service == "booking-service"


def test_new_event_idempotency_key_is_deterministic():
    kw = dict(source_service="s", actor_id="service:x", entity_type="property", entity_id="7")
    a, b = new_event("property.updated", **kw), new_event("property.updated", **kw)
    assert a.idempotency_key == b.idempotency_key
    assert a.event_id != b.event_id


def test_round_trip_encode_decode():
    env = EventEnvelope.model_validate(valid_dict())
    assert decode_event(encode_event(env)) == env


def test_timestamp_normalised_to_utc():
    env = EventEnvelope.model_validate(valid_dict(timestamp="2026-11-11T13:05:00-08:00"))
    assert env.timestamp.utcoffset().total_seconds() == 0
    assert env.timestamp.hour == 21


@pytest.mark.parametrize("event_type", ["debate.round.0", "ai.results", "review.created"])
def test_known_event_type_shapes_accepted(event_type):
    EventEnvelope.model_validate(valid_dict(event_type=event_type))


@pytest.mark.parametrize("actor", ["guest:1001", "host:7", "admin:1", "service:booking-worker", "system:cron_1"])
def test_actor_id_formats_accepted(actor):
    EventEnvelope.model_validate(valid_dict(actor_id=actor))


# ---------- negative ----------

@pytest.mark.parametrize("missing", [f for f in ENVELOPE_FIELDS if f != "payload"])
def test_missing_required_field_rejected(missing):
    d = valid_dict()
    d.pop(missing)
    with pytest.raises(EnvelopeValidationError):
        encode_event(d)


@pytest.mark.parametrize("bad", ["not-a-uuid", "", "c1d2e3f4-5a6b-1c7d-8e9f-0a1b2c3d4e5f"])  # last is UUID1
def test_bad_event_id_rejected(bad):
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(event_id=bad))


@pytest.mark.parametrize("bad", [0, -1, "x"])
def test_bad_schema_version_rejected(bad):
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(schema_version=bad))


@pytest.mark.parametrize("bad", ["", "x" * 65])
def test_bad_source_service_rejected(bad):
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(source_service=bad))


@pytest.mark.parametrize("bad", ["user_42", "guest:", "guest-42", "robot:1", "guest:a b", "Guest:1"])
def test_bad_actor_id_rejected(bad):
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(actor_id=bad))


@pytest.mark.parametrize("bad", ["booking", "user", "", "Reservation"])
def test_unknown_entity_type_rejected(bad):
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(entity={"entity_type": bad, "entity_id": "x"}))


def test_new_event_rejects_bad_input():
    with pytest.raises(EnvelopeValidationError):
        new_event("booking.requested", source_service="booking-service", actor_id="user_1",
                  entity_type="reservation", entity_id="r1")


def test_naive_timestamp_rejected():
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(timestamp=datetime(2026, 11, 11, 12, 0).isoformat()))


@pytest.mark.parametrize("bad", ["Booking.Requested", "booking", "booking..x", "booking requested"])
def test_bad_event_type_rejected(bad):
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(event_type=bad))


def test_entity_requires_type_and_id():
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(entity={"entity_type": "reservation"}))
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(entity={"entity_type": "reservation", "entity_id": ""}))


def test_unknown_top_level_field_rejected():
    with pytest.raises(EnvelopeValidationError):
        encode_event(valid_dict(extra_field="nope"))


def test_decode_rejects_malformed_json():
    with pytest.raises(EnvelopeValidationError):
        decode_event(b"{not json")


# ---------- producer (KafkaProducer mocked) ----------

class _FakeFuture:
    def get(self, timeout=None):
        return "sent"


class _FakeKafkaProducer:
    instances: list = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.sent = []
        _FakeKafkaProducer.instances.append(self)

    def send(self, topic, key=None, value=None, headers=None):
        self.sent.append({"topic": topic, "key": key, "value": value, "headers": headers})
        return _FakeFuture()

    def flush(self):
        pass

    def close(self):
        pass


@pytest.fixture
def producer(monkeypatch):
    fake = types.ModuleType("kafka")
    fake.KafkaProducer = _FakeKafkaProducer
    monkeypatch.setitem(sys.modules, "kafka", fake)
    from shared.kafka.producer import EnvelopeProducer

    return EnvelopeProducer("localhost:9091")


def test_publish_keeps_acks_and_retries(producer):
    assert producer._producer.kwargs["acks"] == "all"
    assert producer._producer.kwargs["retries"] == 3


def test_publish_defaults_key_to_entity_id_and_sets_headers(producer):
    producer.publish("booking.requested", valid_dict())
    sent = producer._producer.sent[0]
    assert sent["key"] == b"9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d"
    assert dict(sent["headers"]) == {"trace_id": b"7f3c9a2e-1b4d-4e8a-9c6f-2d5b8e1a0c47",
                                     "event_type": b"booking.requested"}


def test_publish_uses_explicit_key(producer):
    producer.publish("booking.requested", valid_dict(), key="2001")
    assert producer._producer.sent[0]["key"] == b"2001"


def test_publish_rejects_event_type_topic_mismatch(producer, caplog):
    with caplog.at_level(logging.WARNING, logger="shared.kafka.producer"):
        with pytest.raises(EnvelopeValidationError, match="event_type must equal the topic name"):
            producer.publish("booking.approved", valid_dict())
    assert producer._producer.sent == []
    line = json.loads(caplog.records[-1].getMessage())
    assert line["msg"] == "envelope_rejected"
    assert line["topic"] == "booking.approved"
    assert line["event_type"] == "booking.requested"
    assert set(line) == {"msg", "topic", "event_type", "trace_id", "reason"}


def test_publish_rejects_invalid_envelope_and_logs(producer, caplog):
    with caplog.at_level(logging.WARNING, logger="shared.kafka.producer"):
        with pytest.raises(EnvelopeValidationError):
            producer.publish("booking.requested", valid_dict(actor_id="nobody"))
    assert json.loads(caplog.records[-1].getMessage())["msg"] == "envelope_rejected"
    assert producer._producer.sent == []


def test_publish_raw_only_for_dlq(producer):
    producer.publish_raw("booking.requested.dlq", b"{}")
    with pytest.raises(ValueError):
        producer.publish_raw("booking.requested", b"{}")


# ---------- DLQ record ----------

def test_dlq_record_has_exactly_ten_keys():
    rec = json.loads(build_dlq_record(
        original_topic="booking.requested", partition=1, offset=4182, trace_id=None,
        error_code="ENVELOPE_INVALID", failure_reason="x" * 900, attempts=1,
        consumer_group="booking-worker", raw_message=b"\xff{bad",
    ))
    assert set(rec) == set(DLQ_KEYS) and len(rec) == 10
    assert rec["trace_id"] is None
    assert len(rec["failure_reason"]) == 500
    assert rec["failed_at"].endswith("Z")
    assert rec["raw_message"] == "�{bad"


# ---------- consumer processing ----------

def _collect():
    out = []
    return out, lambda topic, value, headers: out.append((topic, json.loads(value)))


def test_handle_message_dispatches_valid_event():
    seen = []
    assert handle_message("booking.requested", raw(), seen.append)
    assert seen[0].entity.entity_id == "9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d"


def test_handle_message_routes_invalid_to_dlq():
    dlq, send = _collect()
    ok = handle_message("booking.requested", b'{"event_type": "x", "trace_id": "t-1"}', lambda e: None,
                        send_to_dlq=send, partition=0, offset=5, consumer_group="booking-worker")
    assert ok is False
    topic, rec = dlq[0]
    assert topic == "booking.requested.dlq"
    assert rec["error_code"] == "ENVELOPE_INVALID" and rec["attempts"] == 1
    assert rec["trace_id"] == "t-1" and rec["offset"] == 5


def test_unparseable_message_dlq_has_null_trace_id():
    dlq, send = _collect()
    assert not handle_message("booking.requested", b"{not json", lambda e: None, send_to_dlq=send)
    assert dlq[0][1]["trace_id"] is None


def test_topic_mismatch_goes_to_dlq():
    dlq, send = _collect()
    status, _ = process_message("booking.approved", raw(), lambda e: None, send)
    assert status == "dlq"
    assert dlq[0][0] == "booking.approved.dlq"
    assert dlq[0][1]["error_code"] == "ENVELOPE_TOPIC_MISMATCH"


def test_transient_error_retries_then_succeeds():
    calls, sleeps = [], []

    def handler(e):
        calls.append(1)
        if len(calls) < 3:
            raise TransientError("db timeout")

    status, _ = process_message("booking.requested", raw(), handler, None, sleep=sleeps.append)
    assert status == "ok" and len(calls) == 3 and sleeps == [1, 2]


def test_transient_error_exhausts_retries():
    dlq, send = _collect()
    sleeps = []

    def handler(e):
        raise TransientError("db down")

    status, _ = process_message("booking.requested", raw(), handler, send, sleep=sleeps.append)
    assert status == "dlq" and sleeps == [1, 2]
    assert dlq[0][1]["error_code"] == "RETRIES_EXHAUSTED" and dlq[0][1]["attempts"] == 3


@pytest.mark.parametrize("exc", [PermanentError("bad payload"), KeyError("x")])
def test_permanent_or_unexpected_error_dlq_immediately(exc):
    dlq, send = _collect()
    calls = []

    def handler(e):
        calls.append(1)
        raise exc

    status, _ = process_message("booking.requested", raw(), handler, send, sleep=lambda s: None)
    assert status == "dlq" and len(calls) == 1
    assert dlq[0][1]["error_code"] == "HANDLER_FAILED" and dlq[0][1]["attempts"] == 1
