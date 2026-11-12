# Analytics & Observability Service

**Owner:** Eric Zhao
**Port:** 8151 (env `ANALYTICS_SERVICE_PORT`)
**Swagger:** http://localhost:8151/docs
**Dependencies:** mysql, mongodb, kafka

Event analytics, metrics, and observability dashboards.

## Run

```bash
./scripts/start-service.sh analytics-service   # from the repository root
```

## Test

```bash
./scripts/run-tests.sh analytics-service
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
