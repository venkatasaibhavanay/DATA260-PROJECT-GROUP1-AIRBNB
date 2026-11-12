# Shared Kafka contracts

## Event envelope

Every message on every topic is a JSON `EventEnvelope`:

```json
{
  "event_type": "booking.requested",
  "trace_id": "5f0c9a3e-...",
  "timestamp": "2026-11-11T21:05:00Z",
  "actor_id": "user_42",
  "entity": { "entity_type": "booking", "entity_id": "bk_1001" },
  "payload": { "property_id": "prop_7", "check_in": "2026-12-01", "check_out": "2026-12-05" },
  "idempotency_key": "booking.requested:bk_1001"
}
```

- Validate **before publishing** (`new_event`, `encode_event`, `EnvelopeProducer.publish`)
  and **after consuming** (`decode_event`, `handle_message`).
- Unknown top-level fields are rejected. Put domain data in `payload`.
- `timestamp` must include a timezone. It's normalised to UTC.
- Message key = `entity.entity_id`, so one entity's events stay in order.

## Topics

Defined in [`topics.txt`](topics.txt) (single source of truth) and created by the
`kafka-init` container. Each topic `X` has a dead-letter topic `X.dlq`.

| Topic | Producer | Typical consumers |
|---|---|---|
| property.viewed / property.saved | property-service | ai-service, analytics-service |
| booking.requested / approved / cancelled | booking-service | messaging-review-service, analytics-service |
| message.sent / review.created | messaging-review-service | analytics-service |
| ai.requests | any service / frontend via API | ai-service |
| debate.round.0 / 1 / 2 | ai-service agents | ai-service agents |
| ai.results | ai-service | requesting service, analytics-service |

## Dead-letter convention

A message that fails envelope validation, or fails processing after retries, is
published unchanged to `<topic>.dlq` with headers `error` and `source_topic`.
Never drop invalid messages silently.
