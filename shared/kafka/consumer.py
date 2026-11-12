"""Consumer-side helper: validate every message, route invalid ones to the DLQ.

Full consumer loops (group ids, offsets, retries) are implemented by each
service later; this only fixes the validation + dead-letter contract.
"""
from typing import Callable, Optional

from shared.kafka.envelope import EnvelopeValidationError, EventEnvelope, decode_event
from shared.kafka.topics import dlq_topic


def handle_message(
    topic: str,
    raw_value: bytes,
    handler: Callable[[EventEnvelope], None],
    send_to_dlq: Optional[Callable[[str, bytes, list[tuple[str, bytes]]], None]] = None,
) -> bool:
    """Validate and dispatch one message. Returns True if handled, False if dead-lettered."""
    try:
        event = decode_event(raw_value)
    except EnvelopeValidationError as exc:
        if send_to_dlq is not None:
            send_to_dlq(dlq_topic(topic), raw_value,
                        [("error", str(exc)[:500].encode("utf-8")),
                         ("source_topic", topic.encode("utf-8"))])
        return False
    handler(event)
    return True
