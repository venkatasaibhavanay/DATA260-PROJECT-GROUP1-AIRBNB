"""Consumer-side helpers: validation, retries, dead-lettering and the consumer loop.

Contract (API doc sections 3.2 and 3.3):
  * Every message is decoded and validated with decode_event.
  * Malformed messages and event_type/topic mismatches go to "<topic>.dlq"
    immediately, without retrying.
  * Handlers raise TransientError for retryable failures (DB timeout, broker
    down): up to 3 attempts in total, waiting 1 s, 2 s, then 4 s.
  * Handlers raise PermanentError (or anything else) for non-retryable failures,
    which go straight to the DLQ.
  * Offsets are committed only after the handler returns (i.e. after the
    caller's DB transaction commits) or after the DLQ record is published.
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from shared.kafka.envelope import EnvelopeValidationError, EventEnvelope, decode_event
from shared.kafka.topics import dlq_topic

logger = logging.getLogger("shared.kafka.consumer")

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1, 2, 4)

DLQ_KEYS = (
    "original_topic", "partition", "offset", "trace_id", "error_code",
    "failure_reason", "attempts", "failed_at", "consumer_group", "raw_message",
)


class TransientError(Exception):
    """Retryable failure (database timeout, broker unavailable, ...)."""


class PermanentError(Exception):
    """Non-retryable failure; the message goes straight to the DLQ."""


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _trace_id_from_raw(raw: bytes | str) -> Optional[str]:
    """Best-effort trace_id from a message that may not be a valid envelope."""
    try:
        data = json.loads(raw)
        tid = data.get("trace_id") if isinstance(data, dict) else None
        return tid if isinstance(tid, str) and tid else None
    except (ValueError, TypeError):
        return None


def build_dlq_record(
    *,
    original_topic: str,
    partition: Optional[int],
    offset: Optional[int],
    trace_id: Optional[str],
    error_code: str,
    failure_reason: str,
    attempts: int,
    consumer_group: Optional[str],
    raw_message: bytes | str,
    failed_at: Optional[str] = None,
) -> bytes:
    """Dead-letter record as UTF-8 JSON bytes with exactly the 10 documented keys.

    trace_id is null when the message could not be parsed.
    """
    raw_text = raw_message.decode("utf-8", errors="replace") if isinstance(raw_message, bytes) else raw_message
    record = {
        "original_topic": original_topic,
        "partition": partition,
        "offset": offset,
        "trace_id": trace_id,
        "error_code": error_code,
        "failure_reason": str(failure_reason)[:500],
        "attempts": attempts,
        "failed_at": failed_at or _utc_now_z(),
        "consumer_group": consumer_group,
        "raw_message": raw_text,
    }
    return json.dumps(record).encode("utf-8")


SendToDlq = Callable[[str, bytes, list[tuple[str, bytes]]], None]


def process_message(
    topic: str,
    raw_value: bytes,
    handler: Callable[[EventEnvelope], None],
    send_to_dlq: Optional[SendToDlq],
    *,
    partition: Optional[int] = None,
    offset: Optional[int] = None,
    consumer_group: Optional[str] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str, Optional[EventEnvelope]]:
    """Validate, dispatch with retries, dead-letter on failure.

    Returns ("ok" | "dlq", event-or-None). Never raises for handler errors.
    """
    def dlq(trace_id, code, reason, attempts):
        if send_to_dlq is None:
            return
        record = build_dlq_record(
            original_topic=topic, partition=partition, offset=offset, trace_id=trace_id,
            error_code=code, failure_reason=reason, attempts=attempts,
            consumer_group=consumer_group, raw_message=raw_value,
        )
        send_to_dlq(dlq_topic(topic), record,
                    [("error_code", code.encode("utf-8")),
                     ("source_topic", topic.encode("utf-8"))])

    try:
        event = decode_event(raw_value)
    except EnvelopeValidationError as exc:
        dlq(_trace_id_from_raw(raw_value), "ENVELOPE_INVALID", str(exc), 1)
        return "dlq", None

    if event.event_type != topic:
        dlq(event.trace_id, "ENVELOPE_TOPIC_MISMATCH",
            f"event_type {event.event_type!r} does not match topic {topic!r}", 1)
        return "dlq", event

    attempts = 0
    while True:
        attempts += 1
        try:
            handler(event)
            return "ok", event
        except TransientError as exc:
            if attempts >= MAX_ATTEMPTS:
                dlq(event.trace_id, "RETRIES_EXHAUSTED", f"{type(exc).__name__}: {exc}", attempts)
                return "dlq", event
            sleep(BACKOFF_SECONDS[attempts - 1])
        except Exception as exc:  # noqa: BLE001 - PermanentError and anything unexpected
            dlq(event.trace_id, "HANDLER_FAILED", f"{type(exc).__name__}: {exc}", attempts)
            return "dlq", event


def handle_message(
    topic: str,
    raw_value: bytes,
    handler: Callable[[EventEnvelope], None],
    send_to_dlq: Optional[SendToDlq] = None,
    **kwargs: Any,
) -> bool:
    """Validate and dispatch one message. Returns True if handled, False if dead-lettered.

    send_to_dlq(dlq_topic, record_bytes, headers) receives a build_dlq_record() record.
    """
    status, _ = process_message(topic, raw_value, handler, send_to_dlq, **kwargs)
    return status == "ok"


def run_consumer(
    topics: list[str],
    group_id: str,
    handler: Callable[[EventEnvelope], None],
    *,
    bootstrap_servers: str,
    client_id: str,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """Blocking consumer loop with manual commits, retries and DLQ routing.

    Run it in its own process or thread. Set stop_event to stop cleanly.
    Make handler idempotent with shared.kafka.idempotency.
    """
    from kafka import KafkaConsumer, OffsetAndMetadata, TopicPartition  # lazy: tests need no broker

    from shared.kafka.producer import EnvelopeProducer

    stop_event = stop_event or threading.Event()
    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        client_id=client_id,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    dlq_producer = EnvelopeProducer(bootstrap_servers, client_id=f"{client_id}-dlq")

    def send_to_dlq(topic: str, value: bytes, headers: list[tuple[str, bytes]]):
        dlq_producer.publish_raw(topic, value, headers)

    try:
        while not stop_event.is_set():
            batches = consumer.poll(timeout_ms=1000)
            for tp, messages in batches.items():
                for msg in messages:
                    if stop_event.is_set():
                        break
                    started = time.monotonic()
                    status, event = process_message(
                        msg.topic, msg.value, handler, send_to_dlq,
                        partition=msg.partition, offset=msg.offset, consumer_group=group_id,
                    )
                    # Commit only after the handler returned or the DLQ record was published.
                    try:
                        meta = OffsetAndMetadata(msg.offset + 1, None, -1)
                    except TypeError:  # older kafka-python signature
                        meta = OffsetAndMetadata(msg.offset + 1, None)
                    consumer.commit({TopicPartition(msg.topic, msg.partition): meta})
                    logger.info(json.dumps({
                        "msg": "message_processed",
                        "topic": msg.topic,
                        "partition": msg.partition,
                        "offset": msg.offset,
                        "event_type": event.event_type if event else None,
                        "trace_id": event.trace_id if event else _trace_id_from_raw(msg.value),
                        "status": status,
                        "latency_ms": round((time.monotonic() - started) * 1000, 2),
                    }))
                if stop_event.is_set():
                    break
    finally:
        consumer.close()
        dlq_producer.close()
