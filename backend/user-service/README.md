# User & Host Service

**Owner:** Nathan Pak
**Port:** 8101 (env `USER_SERVICE_PORT`)
**Swagger:** http://localhost:8101/docs
**Dependencies:** mysql, redis, kafka

User accounts, guest and host profiles, authentication.

## Run

```bash
./scripts/start-service.sh user-service   # from the repository root
```

## Test

```bash
./scripts/run-tests.sh user-service
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
