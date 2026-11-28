# User & Host Service

**Owner:** Nathan Pak · **Port:** 8101 (`USER_SERVICE_PORT`) · **Swagger:** http://localhost:8101/docs
**Stores:** MySQL (`guests`, `hosts`, `admins`, `host_thread_responses`, `user_processed_events`), Redis (JWT denylist, login rate limit)
**Produces:** `user.registered`, `guest.deleted` · **Consumes:** `property.saved`, `property.unsaved`, `booking.approved`, `message.sent`

Accounts, sign-in, guest and host profiles. Contract: API design document section 6.

Schema diagram, indexes and sample rows: [`docs/schema/user-service.md`](../../docs/schema/user-service.md).

## Endpoints (all under `/api/v1`)

| Route | Auth | Notes |
|---|---|---|
| `POST /auth/login` | public | `{email, password, role}`; 5 failed tries per email per 15 min → 429 |
| `POST /auth/logout` | any user | 204; denylists the token |
| `GET /auth/me` | any user | restore the signed-in user after a refresh |
| `POST /guests/create` | public | 201 + token; publishes `user.registered` |
| `POST /guests/get` | guest (own), host, admin | hosts get the public subset only |
| `POST /guests/update` | guest (own) | only supplied fields change; `preferences` is replaced whole |
| `POST /guests/delete` | guest (own) | soft delete, email/phone anonymized, token revoked; publishes `guest.deleted` |
| `POST /guests/search` | host, admin | `{q, location, page, page_size}`; admins also see email |
| `POST /hosts/create` | public | 201 + token; publishes `user.registered` |
| `POST /hosts/get` | any user | email/phone/access_level only for the host themself or admin |
| `POST /hosts/update` | host (own), admin | `verification_status`/`access_level` admin only |
| `POST /users/profile-photo` | guest, host | multipart `file`, JPEG/PNG ≤ 5 MB; served at `/media/...` |

Events are published **before** the DB commit: if Kafka is down, signup/delete return 503 and nothing is saved.

## Run

```bash
./scripts/infra.sh up                     # MySQL, MongoDB, Redis, Kafka
./scripts/start-service.sh user-service   # API on :8101
```

Tables come from `database/mysql/02_users.sql`, which MySQL runs only on an **empty** volume. If your
MySQL volume already existed before this file, apply it once:

```bash
docker exec -i data260-g1-mysql sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < database/mysql/02_users.sql
```

Consumers (separate process, consumer groups `user-counters` and `user-host-metrics`):

```bash
cd backend/user-service && PYTHONPATH=.:../.. ../../.venv/bin/python -m app.workers
```

Load sample guests and hosts (safe to re-run; password `SamplePass1`; add `--publish-events` to also send
`user.registered` to Kafka):

```bash
cd backend/user-service && PYTHONPATH=.:../.. ../../.venv/bin/python -m app.seed
```

Seed the admin account (password is prompted):

```bash
cd backend/user-service && PYTHONPATH=.:../.. ../../.venv/bin/python -m app.seed_admin --email admin@group1.dev
```

## Test

```bash
./scripts/run-tests.sh user-service   # SQLite in-memory; no Docker needed
```

## For other services

- Identity: use `shared.auth` (`require_role`, `get_current_user`); `user.user_id` is the guest/host id.
- Frontend: `useAuth()` from `frontend/src/context/AuthContext.jsx` gives `{ user, signIn, signOut }`;
  `user` is `{ id, role, name, email }`. API calls already carry the token (`services/api.js`).
- Counters: publish `property.saved`/`property.unsaved` with `payload.guest_id`, and `booking.approved`
  with `payload.guest_id`; `message.sent` needs `thread_id, sender_id, receiver_id, timestamp`,
  `is_first_guest_message` and, on host replies, `reply_to_guest_message_at`. Ids may be `1001` or `"guest:1001"`.

## Layout

| Folder | Contents |
|---|---|
| `app/routes/` | HTTP layer: `auth.py`, `guests.py`, `hosts.py` (+ photo upload) |
| `app/schemas/` | request/response models and validation |
| `app/services/` | business rules, password hashing, Kafka publishing, rate limit, photo storage |
| `app/repositories/` | data access layer (all SQL) |
| `app/models/` | SQLAlchemy entities |
| `app/workers/` | Kafka consumers (`python -m app.workers`) |
| `tests/` | API and consumer tests |
