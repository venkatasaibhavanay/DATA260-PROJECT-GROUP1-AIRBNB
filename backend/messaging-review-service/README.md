# Messaging & Reviews Service

**Owner:** Srija Taduri
**Port:** 8131 (env `MESSAGING_REVIEW_SERVICE_PORT`)
**Swagger:** http://localhost:8131/docs
**Dependencies:** mongodb, kafka

Guest-host messaging and property/user reviews.

## Run

```bash
./scripts/start-service.sh messaging-review-service   # from the repository root
```

## Test

```bash
./scripts/run-tests.sh messaging-review-service
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
