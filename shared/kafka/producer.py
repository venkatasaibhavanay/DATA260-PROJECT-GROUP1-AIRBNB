"""Thin producer wrapper that refuses to publish invalid envelopes."""
from typing import Any

from shared.kafka.envelope import EventEnvelope, encode_event


class EnvelopeProducer:
    def __init__(self, bootstrap_servers: str, client_id: str = "g1-producer"):
        from kafka import KafkaProducer  # imported lazily so tests don't need a broker

        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            client_id=client_id,
            acks="all",
            retries=3,
        )

    def publish(self, topic: str, envelope: EventEnvelope | dict[str, Any], timeout_s: float = 10):
        """Validate, then publish. Keyed by entity_id so one entity's events stay ordered."""
        value = encode_event(envelope)  # raises EnvelopeValidationError if invalid
        env = envelope if isinstance(envelope, EventEnvelope) else EventEnvelope.model_validate(envelope)
        future = self._producer.send(
            topic,
            key=env.entity.entity_id.encode("utf-8"),
            value=value,
            headers=[("trace_id", env.trace_id.encode("utf-8")),
                     ("event_type", env.event_type.encode("utf-8"))],
        )
        return future.get(timeout=timeout_s)

    def publish_raw(self, topic: str, value: bytes, headers: list[tuple[str, bytes]] | None = None):
        """Unvalidated publish — ONLY for dead-letter topics."""
        return self._producer.send(topic, value=value, headers=headers or []).get(timeout=10)

    def close(self):
        self._producer.flush()
        self._producer.close()
