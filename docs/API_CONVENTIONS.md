# API Conventions

These apply to all six services. The submitted API design document is the source of truth;
this page summarizes the shared rules and where they are implemented in `shared/`.

## Routes

- Action-style routes, as in project spec section 6: `POST /api/v1/<resource>/<action>` with a
  JSON body, e.g. `POST /api/v1/properties/search`, `POST /api/v1/bookings/approve`.
- IDs for reads go in the JSON body, not the path.
- `GET` is used only for analytics and AI read routes, e.g. `GET /api/v1/analytics/funnel`,
  `GET /api/v1/ai/tasks/{task_id}`.
- WebSockets: `/ws/...` (bookings, messages, property availability) and
  `/api/v1/ai/tasks/{task_id}/stream`. Authenticate with `?token=<jwt>`; invalid tokens close with code `4401`.
- Health and docs routes (`/`, `/health`, `/health/dependencies`, `/docs`) stay unversioned.

## Data conventions

- JSON in `snake_case`. Request bodies extend `shared.schemas.StrictModel`, so unknown fields are
  rejected with 422.
- Dates: `YYYY-MM-DD`. Timestamps: UTC ISO 8601 ending in `Z` (`2026-11-02T18:30:00Z`).
- Money: decimal string with two decimals plus currency `"USD"` (`shared.schemas.Money`, `Currency`),
  e.g. `{"amount": "189.00", "currency": "USD"}`. Never floats.
- Stays: `check_in` inclusive, `check_out` exclusive.
- IDs: MySQL IDs are integers; `reservation_id`, `task_id`, `trace_id` and `plan_id` are UUID strings;
  MongoDB IDs are 24-character ObjectId strings. Actor references look like `"guest:1001"`.

## Success responses

```json
{ "data": { ... }, "meta": { "request_id": "uuid", "trace_id": "uuid" } }
```

- Return `shared.responses.ok(data, request)`; use `Envelope[T]` as `response_model` for Swagger.
- `204 No Content` has no body. Health endpoints are not wrapped.
- Lists use `shared.schemas.Page` / `make_page`: `items, page, page_size, total, total_pages`.
  Pagination input: `PageParams` (`page >= 1`, default 1; `page_size` 1-100, default 20).

## Errors

```json
{
  "error": { "code": "VALIDATION_ERROR", "message": "One or more fields are invalid.",
             "fields": { "check_out": "check_out must be after check_in." } },
  "meta": { "request_id": "uuid", "trace_id": "uuid" }
}
```

- Raise `AppError(status_code, code, message, fields=None)` from `shared.errors`.
- Error codes are the ones listed per endpoint in the API doc (no domain prefix required).
- Automatic mappings: validation errors -> 422 `VALIDATION_ERROR`; 400 `BAD_REQUEST`, 401 `UNAUTHORIZED`,
  403 `ROLE_FORBIDDEN`, 404 `NOT_FOUND`, 405 `METHOD_NOT_ALLOWED`, 409 `CONFLICT`, 413 `FILE_TOO_LARGE`,
  415 `UNSUPPORTED_MEDIA_TYPE`, 429 `RATE_LIMITED`, 503 `SERVICE_UNAVAILABLE`; unhandled exceptions ->
  500 `INTERNAL_ERROR` (no stack trace in the body; logged with the trace_id).

## Status codes

| Code | Use |
|---|---|
| 200 | successful read or update |
| 201 | resource created |
| 202 | accepted for async processing (booking request, AI request, event ingest) |
| 204 | successful delete or logout |
| 400 | malformed business request |
| 401 | missing, expired or invalid token |
| 403 | wrong role or not the owner |
| 404 | not found or not visible to the caller |
| 409 | duplicate, conflict, invalid transition, reused idempotency key |
| 413 / 415 | upload too large / unsupported media type |
| 422 | field validation failed |
| 429 | rate limit reached |
| 500 | unexpected server failure |
| 503 | dependency unavailable; request not applied |

## Headers

| Header | Rule |
|---|---|
| `Authorization` | `Bearer <access_token>` on protected routes |
| `X-Trace-ID` | optional; generated if missing; echoed on every response and copied into every Kafka event |
| `X-Request-ID` | optional; generated if missing; echoed on every response and in `meta.request_id` |
| `Idempotency-Key` | required on routes that change reservation state or send a message |

The request-context middleware (installed by `register_exception_handlers`) handles the trace and
request IDs. The frontend client (`frontend/src/services/api.js`) sends all four headers.

## Authentication

- `shared.auth`: JWT HS256 signed with `JWT_SECRET`, 30-minute expiry. Claims: `sub` (`"<role>:<id>"`),
  `role`, `user_id`, `jti`, `iat`, `exp`.
- Roles: `guest`, `host`, `admin`, `service`. Use `get_current_user`, `optional_user`,
  `require_role(...)`; WebSockets use `ws_user_from_token`.
- Identity is read only from the token, never from the request body.
- Logout calls `revoke_token`, which denylists the `jti` in Redis (`g1:auth:denylist:<jti>`) until expiry.

## HTTP idempotency

- Routes that change reservation state or send a message require an `Idempotency-Key` header.
- The owning service stores key, caller, request hash and response for 24 hours in its own store
  (booking: MySQL `idempotency_keys`; messaging: MongoDB `idempotency_keys`).
- Same key + same body returns the stored response. Same key + different body returns
  409 `IDEMPOTENCY_KEY_REUSED`.

## Kafka

- Every message uses the 10-field envelope (`shared.kafka.envelope`): `event_id, event_type,
  schema_version, trace_id, timestamp, source_service, actor_id, entity{entity_type, entity_id},
  idempotency_key, payload`. Build with `new_event(...)`.
- `event_type` must equal the topic name.
- Partition keys (pass `key=` to `EnvelopeProducer.publish`): `property_id` for property,
  availability, booking and review topics; `thread_id` for message topics; `trace_id` for AI topics.
- At-least-once delivery: offsets are committed only after the database commit. Consumers use
  `shared.kafka.consumer.run_consumer`.
- Duplicates: record `(consumer_group, idempotency_key)` in `<prefix>_processed_events`
  (`shared.kafka.idempotency`) in the same transaction.
- Retries: raise `TransientError` for up to 3 attempts with waits of 1 s, 2 s, 4 s; `PermanentError`
  (or anything else) goes straight to the DLQ.
- Dead letters go to `<topic>.dlq` as JSON with `original_topic, partition, offset, trace_id,
  error_code, failure_reason, attempts, failed_at, consumer_group, raw_message`.

## Rate limits

- Login: 5 failed attempts per email per 15 minutes.
- AI: at most 3 active AI tasks per guest.
- Everything else: 100 requests per minute per user.
- Exceeding a limit returns 429 `RATE_LIMITED`.
