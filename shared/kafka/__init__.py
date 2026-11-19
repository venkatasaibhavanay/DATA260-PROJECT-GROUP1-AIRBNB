"""Shared Kafka contracts: event envelope, topic names, producer/consumer helpers."""
from shared.kafka.envelope import (
    ACTOR_ID_PATTERN,
    Entity,
    EnvelopeValidationError,
    EventEnvelope,
    decode_event,
    encode_event,
    new_event,
)
from shared.kafka.topics import ALL_TOPICS, DLQ_SUFFIX, DOMAIN_TOPICS, dlq_topic

__all__ = [
    "Entity", "EventEnvelope", "EnvelopeValidationError", "ACTOR_ID_PATTERN", "new_event",
    "encode_event", "decode_event", "DOMAIN_TOPICS", "ALL_TOPICS", "DLQ_SUFFIX", "dlq_topic",
]
