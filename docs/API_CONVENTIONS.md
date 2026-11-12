# API Conventions

These apply to all six services so the frontend and other services can rely on them.

## URLs

- Feature endpoints: `/api/v1/<plural-resource>`, e.g. `GET /api/v1/bookings/{booking_id}`.
- Lowercase, hyphenated paths. IDs in the path, filters in the query string.
- Service metadata (`/`, `/health`, `/health/dependencies`, `/docs`) stays unversioned.

## Requests & responses

- JSON only. `snake_case` field names.
- Validate every request body with a Pydantic schema in `app/schemas/`.
- Timestamps: ISO 8601 with timezone, UTC (`2026-11-11T21:05:00Z`). Dates: `YYYY-MM-DD`.
- Money: integer cents plus a `currency` field (avoid floats).
- Single resource: return the object itself.
- Lists:

```json
{ "items": [ ... ], "page": 1, "page_size": 20, "total": 134 }
```

## Errors

All errors use one shape (implemented in `shared/errors`):

```json
{
  "error": {
    "code": "BOOKING_DATES_UNAVAILABLE",
    "message": "The property is already booked for these dates.",
    "details": { "property_id": "prop_7" },
    "trace_id": "5f0c9a3e-..."
  }
}
```

Raise expected errors with `AppError(status_code, code, message, details)`.
Validation errors are converted automatically (`code: VALIDATION_ERROR`, status 422).
Error codes: `UPPER_SNAKE_CASE`, prefixed by domain (`USER_`, `PROPERTY_`, `BOOKING_`, `MESSAGE_`, `REVIEW_`, `AI_`, `ANALYTICS_`).

## HTTP status codes

| Code | When |
|---|---|
| 200 OK | successful read / update |
| 201 Created | resource created (include it in the body) |
| 202 Accepted | async work started (e.g. AI request queued on Kafka) |
| 204 No Content | successful delete |
| 400 Bad Request | well-formed but invalid business input |
| 401 Unauthorized | not logged in |
| 403 Forbidden | logged in but not allowed (e.g. guest approving a booking) |
| 404 Not Found | resource doesn't exist |
| 409 Conflict | state conflict (double booking, duplicate idempotency key with different body) |
| 422 Unprocessable Entity | schema validation failed |
| 503 Service Unavailable | a dependency is down |
| 500 | unexpected bug (never on purpose) |

## Trace IDs

- Header: `X-Trace-Id`. The frontend generates one per request (`services/api.js`).
- Services read it (or generate one), log it, return it in error responses, and copy it into
  every Kafka event caused by the request (`trace_id`).
- Service-to-service HTTP calls must forward the same `X-Trace-Id`.

## Idempotency

- **HTTP:** state-changing `POST`s that could be retried (create booking, send message) accept an
  `Idempotency-Key` header. Store key → response. A repeat with the same key returns the stored
  response instead of creating a duplicate.
- **Kafka:** every event has `idempotency_key`. Make it deterministic for the business action
  (e.g. `booking.approved:bk_1001`). Consumers record processed keys and skip duplicates.

## Kafka envelope requirements

| Field | Type | Rule |
|---|---|---|
| `event_type` | string | `domain.action`, lowercase, must match the topic (e.g. `booking.requested`) |
| `trace_id` | string | from the originating request |
| `timestamp` | ISO 8601 | timezone required, stored as UTC |
| `actor_id` | string | user/host/agent/service that caused the event |
| `entity` | object | `{ "entity_type": "booking", "entity_id": "bk_1001" }` |
| `payload` | object | domain data. Keep it small, never secrets |
| `idempotency_key` | string | deterministic per business action |

- Build with `shared.kafka.new_event(...)`. Publish with `EnvelopeProducer.publish(topic, env)`.
- Consume with `shared.kafka.consumer.handle_message(...)`. Invalid messages go to `<topic>.dlq`.
- Unknown top-level fields are rejected. Add new data inside `payload`.
- Changing the envelope itself requires team agreement (see TEAM_RESPONSIBILITIES.md).
