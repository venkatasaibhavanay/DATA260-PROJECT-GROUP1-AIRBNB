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
- Each request carries an `X-Trace-Id` header. Services echo it on errors and copy it into Kafka events.
- CORS on every service allows the origins in `CORS_ORIGINS` (default `http://localhost:5101`).
- Versioned feature routes: `/api/v1/<resource>` (see API_CONVENTIONS.md).

## Database responsibilities

| Store | Used for | Why |
|---|---|---|
| **MySQL** (`airbnb_group1`) | users, hosts, property core records, **bookings**, aggregates | ACID transactions, constraints (e.g. no double-booking), relational joins |
| **MongoDB** (`airbnb_group1`) | rich listing documents, messages, reviews, AI agent state, raw analytics events | flexible schema, nested documents, high write volume |
| **Redis** | search result caching, availability locks, sessions, rate limits | in-memory speed, TTLs, atomic operations |

Rule: **each table/collection has exactly one owning service.** Other services read through
that service's API or react to its events. They never write to its tables.

## Kafka communication

- Single-node KRaft broker (no ZooKeeper). Host clients: `localhost:9091`. Containers: `kafka:29092`.
- Topics are listed in `shared/kafka/topics.txt` and created by the `kafka-init` container.
  Each topic `X` has a dead-letter topic `X.dlq`.
- Every message is a JSON **event envelope** (`shared/kafka/envelope.py`):
  `event_type, trace_id, timestamp, actor_id, entity{entity_type, entity_id}, payload, idempotency_key`.
- Message key = `entity_id`, so events for one booking/property stay in order within a partition.
- Consumers must be **idempotent**: store processed `idempotency_key`s and skip duplicates.

Example flow, a booking:

```
guest ─POST /api/v1/bookings─► booking-service ──(MySQL txn)──► bookings table
                                     │
                                     └─publish booking.requested─► Kafka
                                                                     ├─► analytics-service (metrics)
host ─POST /bookings/{id}/approve─► booking-service ─publish booking.approved─►
                                                                     ├─► messaging-review-service (open thread)
                                                                     └─► analytics-service
```

## Redis caching

- Cache-aside: read Redis → on miss read DB → write Redis with a TTL.
- Key naming: `g1:<service>:<entity>:<id>` (e.g. `g1:property:search:<hash>`).
- Invalidate on writes, or react to Kafka events (e.g. clear availability cache on `booking.approved`).
- Locks for booking: `SET g1:booking:lock:<property_id>:<date> <booking_id> NX EX 30`.

## Agentic AI services

- `ai-service` consumes `ai.requests` and runs a multi-agent "debate":
  agents publish to `debate.round.0` → `debate.round.1` → `debate.round.2`, each round reading the previous one.
- The final answer is published to `ai.results` with the original `trace_id`, so the requester
  (and analytics) can correlate it.
- Agent state/transcripts live in MongoDB. Repeated prompts may be cached in Redis.
- Behavioural signals (`property.viewed`, `property.saved`) feed recommendations.

## Analytics & observability

- `analytics-service` consumes all domain topics, stores raw events in MongoDB, and maintains
  aggregates (bookings/day, conversion, popular properties) in MySQL.
- Observability: every service exposes `/health` (process) and `/health/dependencies` (live probes).
  `trace_id` ties an HTTP request to every event it causes.
- The analytics frontend page shows metrics and service health.

## Health semantics

| Endpoint | Checks | Use for |
|---|---|---|
| `GET /health` | process only. Returns `"dependencies": "not_checked"` | liveness |
| `GET /health/dependencies` | live connection to each dependency, 503 if any fail | readiness / debugging |
