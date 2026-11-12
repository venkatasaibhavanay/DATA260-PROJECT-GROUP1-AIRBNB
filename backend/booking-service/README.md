# Booking & Reservations Service

**Owner:** Venkata Sai Bhavana Yarrapragada
**Port:** 8121 (env `BOOKING_SERVICE_PORT`)
**Swagger:** http://localhost:8121/docs
**Dependencies:** mysql, redis, kafka

Booking requests, approvals, cancellations, and reservation lifecycle.

## Run

```bash
./scripts/start-service.sh booking-service   # from the repository root
```

## Test

```bash
./scripts/run-tests.sh booking-service
```

## Layout

| Folder | Put here |
|---|---|
| `app/routes/` | FastAPI routers (thin HTTP layer) |
| `app/schemas/` | Pydantic request/response models |
| `app/services/` | Business logic |
| `app/models/` | SQLAlchemy models / document shapes |
| `app/database/` | Connection helpers |
| `app/kafka/` | Topic usage, producers, consumers |
| `tests/` | pytest tests |
