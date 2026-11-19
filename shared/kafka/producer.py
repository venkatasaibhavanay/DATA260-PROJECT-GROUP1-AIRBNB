"""Thin producer wrapper that refuses to publish invalid envelopes."""
import json
import logging
from typing import Any

from pydantic import ValidationError

from shared.kafka.envelope import EnvelopeValidationError, EventEnvelope, encode_event
from shared.kafka.topics import DLQ_SUFFIX

logger = logging.getLogger("shared.kafka.producer")


class EnvelopeProducer:
    def __init__(self, bootstrap_servers: str, client_id: str = "g1-producer"):
        from kafka import KafkaProducer  # imported lazily so tests don't need a broker

        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            client_id=client_id,
            acks="all",
            retries=3,
        )

    def publish(
        self,
        topic: str,
        envelope: EventEnvelope | dict[str, Any],
        key: str | None = None,
        timeout_s: float = 10,
    ):
        """Validate, then publish.

        Rules:
          * event_type must equal the topic name (except on ``*.dlq`` topics).
          * ``key`` defaults to ``entity.entity_id``. Callers MUST pass the
            partition key the API doc (section 3.3) requires:
              - property_id for property.*, availability.*, booking.* and review.* topics
              - thread_id for message.* topics
              - trace_id for AI topics (ai.*, debate.round.*)
        On any validation failure one WARNING line is logged as JSON
        ``{"msg": "envelope_rejected", ...}`` and EnvelopeValidationError is raised.
        """
        raw = envelope if isinstance(envelope, dict) else None
        try:
            try:
                env = envelope if isinstance(envelope, EventEnvelope) else EventEnvelope.model_validate(envelope)
            except ValidationError as exc:
                raise EnvelopeValidationError(str(exc)) from exc
            if not topic.endswith(DLQ_SUFFIX) and env.event_type != topic:
                raise EnvelopeValidationError("event_type must equal the topic name")
            value = encode_event(env)
        except EnvelopeValidationError as exc:
            src = raw if raw is not None else envelope.model_dump()  # type: ignore[union-attr]
            logger.warning(json.dumps({
                "msg": "envelope_rejected",
                "topic": topic,
                "event_type": src.get("event_type"),
                "trace_id": src.get("trace_id"),
                "reason": str(exc)[:500],
            }, default=str))
            raise

        partition_key = key if key is not None else env.entity.entity_id
        future = self._producer.send(
            topic,
            key=str(partition_key).encode("utf-8"),
            value=value,
            headers=[("trace_id", env.trace_id.encode("utf-8")),
                     ("event_type", env.event_type.encode("utf-8"))],
        )
        return future.get(timeout=timeout_s)

    def publish_raw(self, topic: str, value: bytes, headers: list[tuple[str, bytes]] | None = None,
                    key: bytes | None = None):
        """Unvalidated publish. ONLY for dead-letter (``*.dlq``) topics."""
        if not topic.endswith(DLQ_SUFFIX):
            raise ValueError("publish_raw is only allowed for .dlq topics")
        return self._producer.send(topic, key=key, value=value, headers=headers or []).get(timeout=10)

    def close(self):
        self._producer.flush()
        self._producer.close()
