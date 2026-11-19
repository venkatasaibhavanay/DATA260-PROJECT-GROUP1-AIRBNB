# Architecture

## Three tiers

| Tier | Technology | Responsibility |
|---|---|---|
| Presentation | React 19 + Vite, React Router, Axios (`frontend/`, port 5101) | UI for all six modules in one app. No business rules |
| Application | Six FastAPI microservices (ports 8101–8151) | Each owns one business domain, its API, and its data |
| Data | MySQL 8.4, MongoDB 7, Redis 7.4, Kafka 3.9 (Docker) | Durable storage, caching, asynchronous events |

Services are **independently runnable and deployable**. They do not import each other's code.
They share only the `shared/` package (contracts, config, error format) and talk to each
other through **REST** (synchronous queries) or **Kafka** (asynchronous events).

## Frontend → backend

- One Axios client per service, created in `frontend/src/services/api.js` from `VITE_*_API_URL`.
- Each request carries `X-Trace-ID` and `X-Request-ID` headers (plus `Authorization` and, where required,
  `Idempotency-Key`). Services echo both IDs on every response and copy the trace ID into Kafka events.
- CORS on every service allows the origins in `CORS_ORIGINS` (default `http://localhost:5101`).
- Versioned action-style routes: `POST /api/v1/<resource>/<action>` (see API_CONVENTIONS.md).

## Database responsibilities

| Store | Used for | Why |
|---|---|---|
| **MySQL** (`airbnb_group1`) | guests, hosts, properties, availability, **reservations** and `reservation_nights` | ACID transactions and constraints. Double booking is prevented with a MySQL row lock on the property plus `UNIQUE(property_id, night_date)`, not Redis locks |
| **MongoDB** (`airbnb_group1`) | message threads, messages, reviews, AI agent state, **analytics events and rollups** | flexible schema, nested documents, high write volume. Analytics stores events and rollups in MongoDB, not MySQL aggregates |
| **Redis** | property search/detail/availability cache, JWT denylist | in-memory speed, TTLs |

Rule: **each table/collection has exactly one owning service.** Other services read through
that service's API or react to its events. They never write to its tables.

## Kafka communication

- Single-node KRaft broker (no ZooKeeper). Host clients: `localhost:9091`. Containers: `kafka:29092`.
- Topics are listed in `shared/kafka/topics.txt` and created by the `kafka-init` container.
  Each topic `X` has a dead-letter topic `X.dlq`.
- Every message is a JSON **event envelope** (`shared/kafka/envelope.py`) with 10 fields:
  `event_id, event_type, schema_version, trace_id, timestamp, source_service, actor_id,
  entity{entity_type, entity_id}, idempotency_key, payload`. `event_type` must equal the topic.
- Partition key: `property_id` for property, availability, booking and review topics; `thread_id`
  for message topics; `trace_id` for AI topics. This keeps each entity's events in order.
- Consumers must be **idempotent**: record `(consumer_group, idempotency_key)` in
  `<prefix>_processed_events` in the same transaction and skip duplicates.

Example flow, a booking:

```
guest ─POST /api/v1/bookings/request─► booking-service API
          stores the idempotency record, publishes booking.requested (key property_id), returns 202
                                                     │
                                                     ▼
          booking worker process (consumer group booking-worker)
          locks the property row, inserts the reservation and one reservation_nights row per night
          (UNIQUE(property_id, night_date)), publishes booking.pending or booking.rejected
                                                     │
                                                     ▼
          guest is notified over WS /ws/bookings

host ─POST /api/v1/bookings/approve─► booking-service ─publish booking.approved─►
          ├─► property-service: updates availability and Redis cache
          ├─► messaging-review-service: records review eligibility
          └─► analytics-service: records the event
```

## Redis caching

- Cache-aside: read Redis → on miss read DB → write Redis with a TTL.
- Key naming: `g1:<service>:<entity>:<id>` (e.g. `g1:property:search:<hash>`).
- Invalidate on writes, or react to Kafka events (e.g. clear availability cache on `booking.approved`).
- JWT denylist: `g1:auth:denylist:<jti>` with a TTL until the token expires.

## Agentic AI services

- `ai-service` consumes `ai.requests` and runs a multi-agent "debate":
  agents publish to `debate.round.0` → `debate.round.1` → `debate.round.2`, each round reading the previous one.
- The final answer is published to `ai.results` with the original `trace_id`, so the requester
  (and analytics) can correlate it.
- Agent state/transcripts live in MongoDB. Repeated prompts may be cached in Redis.
- Behavioural signals (`property.viewed`, `property.saved`) feed recommendations.

## Analytics & observability

- `analytics-service` consumes all domain topics and all `.dlq` topics, and stores events,
  service logs, DLQ records and rollups in MongoDB.
- Observability: every service exposes `/health` (process) and `/health/dependencies` (live probes).
  `trace_id` ties an HTTP request to every event it causes.
- The analytics frontend page shows metrics and service health.

## Health semantics

| Endpoint | Checks | Use for |
|---|---|---|
| `GET /health` | process only. Returns `"dependencies": "not_checked"` | liveness |
| `GET /health/dependencies` | live connection to each dependency, 503 if any fail | readiness / debugging |
