# Property & Search Service

**Owner:** Sanjana Reddy Katham
**Port:** 8111 (env `PROPERTY_SERVICE_PORT`)
**Swagger:** http://localhost:8111/docs
**Dependencies:** mysql, mongodb, redis, kafka

Property listings, availability metadata, and search.

## Run

```bash
./scripts/start-service.sh property-service   # from the repository root
```

## Test

```bash
./scripts/run-tests.sh property-service
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
