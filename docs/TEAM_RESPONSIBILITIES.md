# Team Responsibilities: Group 1

Each member owns a **vertical slice**: React pages, a FastAPI service, its data,
its Kafka events, validation and error handling, tests, and API docs.

| Member | Module | Frontend folder | Service (port) | Data | Kafka (produces → consumes) | Branch |
|---|---|---|---|---|---|---|
| Nathan Pak | User & Host Profiles + shared setup | `pages/users` | `user-service` (8101) | MySQL users/hosts, Redis sessions | — | `feature/users-nathan` |
| Sanjana Reddy Katham | Property & Search | `pages/properties` | `property-service` (8111) | MySQL listings, MongoDB rich listing docs, Redis search cache | `property.viewed`, `property.saved` | `feature/properties-sanjana` |
| Venkata Sai Bhavana Yarrapragada | Booking & Reservations | `pages/bookings` | `booking-service` (8121) | MySQL bookings (transactional), Redis availability locks | `booking.requested`, `booking.approved`, `booking.cancelled` | `feature/bookings-bhavana` |
| Srija Taduri | Messaging & Reviews | `pages/messaging-reviews` | `messaging-review-service` (8131) | MongoDB messages & reviews | `message.sent`, `review.created` ← `booking.approved` | `feature/messaging-srija` |
| Angela Wai | Agentic AI & Recommendations | `pages/ai` | `ai-service` (8141) | MongoDB agent state, Redis cache | `debate.round.*`, `ai.results` ← `ai.requests`, `property.*` | `feature/ai-angela` |
| Eric Zhao | Analytics & Observability | `pages/analytics` | `analytics-service` (8151) | MongoDB event store, MySQL aggregates | ← all domain topics | `feature/analytics-eric` |

## Every slice must include

- [ ] React page(s) under `frontend/src/pages/<module>/` using `services/api.js`
- [ ] FastAPI routers in `app/routes/`, schemas in `app/schemas/`, logic in `app/services/`
- [ ] Database tables/collections owned only by this service (`database/mysql/NN_<module>.sql`)
- [ ] Kafka events using `shared.kafka.EventEnvelope`, validated before publish and after consume
- [ ] Errors in the standard format (`shared.errors.AppError`)
- [ ] pytest tests in `backend/<service>/tests/`
- [ ] Endpoints documented (Swagger summaries/descriptions + service README)

## Shared ownership

| Area | Default owner | Change process |
|---|---|---|
| `shared/kafka` envelope & topics | whole team | PR + approval from 2 members |
| `infrastructure/docker-compose.yml`, `.env.example` | Nathan (shared setup), Bhavana (initial setup) | PR + 1 approval, announce in team chat |
| `frontend/src/App.jsx`, `NavBar`, `services/api.js` | whole team | keep edits small, rebase often |
| `docs/` | whole team | |
