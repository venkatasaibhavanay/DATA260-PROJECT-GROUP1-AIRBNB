# Team Responsibilities: Group 1

Each member owns a **vertical slice**: React pages, a FastAPI service, its data,
its Kafka events, validation and error handling, tests, and API docs.

| Member | Module | Frontend folder | Service (port) | Data | Kafka (produces → consumes) | Branch |
|---|---|---|---|---|---|---|
| Nathan Pak | User & Host Profiles + shared setup | pages/users | user-service (8101) | MySQL guests, hosts; Redis JWT denylist | user.registered, guest.deleted ← property.saved, property.unsaved, booking.approved, message.sent | feature/users-nathan |
| Sanjana Reddy Katham | Property & Search | pages/properties | property-service (8111) | MySQL properties, property_amenities, property_photos, availability_blocks, saved_properties; Redis search/detail/availability cache | property.created, property.updated, property.deleted, property.viewed, property.saved, property.unsaved, availability.updated ← booking.pending, booking.approved, booking.declined, booking.cancelled, review.created | feature/properties-sanjana |
| Venkata Sai Bhavana Yarrapragada | Booking & Reservations | pages/bookings | booking-service (8121) + booking worker process | MySQL reservations, reservation_nights, reservation_status_history, property_locks, idempotency_keys | booking.requested, booking.pending, booking.rejected, booking.approved, booking.declined, booking.cancelled ← booking.requested, guest.deleted, property.deleted, ai.results | feature/bookings-bhavana |
| Srija Taduri | Messaging & Reviews | pages/messaging-reviews | messaging-review-service (8131) | MongoDB threads, messages, idempotency_keys, reviews, review_eligibility | message.sent, message.read, review.created, review.responded ← message.sent, booking.approved, booking.cancelled | feature/messaging-srija |
| Angela Wei | Agentic AI & Recommendations | pages/ai | ai-service (8141) | MongoDB ai_tasks, plans, debate_messages, votes, feedback, agent_versions, benchmark_runs | ai.requests, ai.parsed, debate.round.0/1/2, ai.results, ai.decisions ← same AI topics | feature/ai-angela |
| Eric Zhao | Analytics & Observability | pages/analytics | analytics-service (8151) | MongoDB event_log, service_logs, dlq_records, rollups | ← all domain topics and all .dlq topics | feature/analytics-eric |

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
