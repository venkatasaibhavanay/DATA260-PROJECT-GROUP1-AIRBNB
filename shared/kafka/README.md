# Shared Kafka contracts

Full rules: API design document section 3 and [`docs/API_CONVENTIONS.md`](../../docs/API_CONVENTIONS.md#kafka).

## Event envelope (10 fields)

```json
{
  "event_id": "c1d2e3f4-5a6b-4c7d-8e9f-0a1b2c3d4e5f",
  "event_type": "booking.requested",
  "schema_version": 1,
  "trace_id": "7f3c9a2e-1b4d-4e8a-9c6f-2d5b8e1a0c47",
  "timestamp": "2026-11-02T18:30:00Z",
  "source_service": "booking-service",
  "actor_id": "guest:1001",
  "entity": { "entity_type": "reservation", "entity_id": "9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d" },
  "idempotency_key": "booking.requested:9b2f6c1e-3d4a-4f5b-8c7d-1e2f3a4b5c6d",
  "payload": { "property_id": 2001, "check_in": "2026-12-18", "check_out": "2026-12-20" }
}
```

- Build with `new_event(event_type, source_service=..., actor_id=..., entity_type=..., entity_id=...)`.
- Publish with `EnvelopeProducer.publish(topic, env, key=...)`. `event_type` must equal the topic.
  Partition key: `property_id` for property/availability/booking/review topics, `thread_id` for
  message topics, `trace_id` for AI topics.
- Consume with `run_consumer(...)`; raise `TransientError` to retry (1 s, 2 s, 4 s) or
  `PermanentError` to dead-letter. Skip duplicates with `shared.kafka.idempotency`.

## Topics

Defined in [`topics.txt`](topics.txt) (single source of truth, 26 topics) and created by the
`kafka-init` container. Each topic `X` has a dead-letter topic `X.dlq`.

## Dead-letter record

`build_dlq_record(...)` produces JSON with exactly: `original_topic, partition, offset, trace_id,
error_code, failure_reason, attempts, failed_at, consumer_group, raw_message`.
Error codes: `ENVELOPE_INVALID`, `ENVELOPE_TOPIC_MISMATCH`, `RETRIES_EXHAUSTED`, `HANDLER_FAILED`.
