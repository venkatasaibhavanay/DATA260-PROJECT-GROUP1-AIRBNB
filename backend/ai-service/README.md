# Agentic AI & Recommendations Service

**Owner:** Angela Wai
**Port:** 8141 (env `AI_SERVICE_PORT`)
**Swagger:** http://localhost:8141/docs
**Dependencies:** mongodb, redis, kafka

Agentic AI workflows and recommendations coordinated through Kafka.

## Run

```bash
./scripts/start-service.sh ai-service   # from the repository root
```

## Test

```bash
./scripts/run-tests.sh ai-service
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
