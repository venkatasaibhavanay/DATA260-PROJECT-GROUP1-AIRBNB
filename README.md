# DATA 260 Group 1: Airbnb-Style Rental & Booking Platform

Distributed microservices project for **DATA 260 Distributed Systems**, San José State University.

React frontend · six FastAPI microservices · MySQL · MongoDB · Redis · Apache Kafka (KRaft) · Docker Compose

---

## Team

| Member | Module (vertical slice) | Service | Port |
|---|---|---|---|
| Nathan Pak | User & Host Profiles + shared setup | `user-service` | 8101 |
| Sanjana Reddy Katham | Property & Search | `property-service` | 8111 |
| Venkata Sai Bhavana Yarrapragada | Booking & Reservations | `booking-service` | 8121 |
| Srija Taduri | Messaging & Reviews | `messaging-review-service` | 8131 |
| Angela Wai | Agentic AI & Recommendations | `ai-service` | 8141 |
| Eric Zhao | Analytics & Observability | `analytics-service` | 8151 |

Details: [docs/TEAM_RESPONSIBILITIES.md](docs/TEAM_RESPONSIBILITIES.md)

## Architecture

```
 React (Vite) :5101
      │  REST (axios, X-Trace-Id)
      ▼
 ┌────────────┬──────────────┬──────────────┬───────────────┬────────────┬──────────────┐
 │ user :8101 │ property     │ booking      │ messaging &   │ ai :8141   │ analytics    │
 │            │ :8111        │ :8121        │ reviews :8131 │            │ :8151        │
 └─────┬──────┴──────┬───────┴──────┬───────┴───────┬───────┴─────┬──────┴──────┬───────┘
       │             │              │               │             │             │
       ▼             ▼              ▼               ▼             ▼             ▼
   MySQL :3311   MongoDB :27101   Redis :6381   ◄──── Kafka :9091 (event envelope) ────►
```

Full explanation: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Repository structure

```
DATA260_Group1_Airbnb/
├── frontend/                 React + Vite + React Router + Axios (one shared app)
│   └── src/{components,pages/<module>,services}/
├── backend/<service>/        six independent FastAPI services
│   ├── app/{main.py,config.py,routes,models,schemas,services,database,kafka}/
│   ├── tests/  requirements.txt  Dockerfile  README.md
├── shared/                   code shared by all services
│   ├── kafka/                event envelope, topics.txt, producer/consumer helpers
│   ├── schemas/  errors/     common response shapes, standard error format
│   └── config.py             infrastructure settings (reads root .env)
├── database/{mysql,mongodb,seed}/   init scripts (run on first container start)
├── infrastructure/docker-compose.yml
├── scripts/                  helper scripts (macOS/Linux bash)
├── tests/                    shared + integration tests
├── docs/
└── .env.example
```

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Git | any recent | |
| Python | **3.11+** (3.12 recommended) | or install [uv](https://docs.astral.sh/uv/), which downloads Python 3.12 for you |
| Node.js | **22 LTS** (≥ 20.19) | npm comes with it |
| Docker Desktop | with Compose v2 | must be running |
| GitHub CLI (`gh`) | optional | easiest GitHub login |

Check what you have: `./scripts/check-prereqs.sh`

## Quick start (any laptop)

```bash
git clone https://github.com/venkatasaibhavanay/data260-group1-airbnb.git
cd data260-group1-airbnb

./scripts/setup-env.sh        # creates .env with random local passwords (git-ignored)
./scripts/setup-python.sh     # creates .venv and installs backend dependencies
./scripts/infra.sh up         # starts MySQL, MongoDB, Redis, Kafka (+ creates topics)
./scripts/start-service.sh booking-service   # or any service; use one terminal per service
./scripts/start-frontend.sh   # http://localhost:5101
```

Windows: use WSL2 (recommended) or Git Bash. Or run the equivalent commands manually (see *Manual commands*).

## Ports

All application ports end in **1** (Group 1). Infrastructure is bound to `127.0.0.1` only.

| Component | Host port | Container port | URL |
|---|---|---|---|
| React frontend | 5101 | — | http://localhost:5101 |
| User & Host Service | 8101 | — | http://localhost:8101/docs |
| Property & Search Service | 8111 | — | http://localhost:8111/docs |
| Booking & Reservations Service | 8121 | — | http://localhost:8121/docs |
| Messaging & Reviews Service | 8131 | — | http://localhost:8131/docs |
| Agentic AI Service | 8141 | — | http://localhost:8141/docs |
| Analytics Service | 8151 | — | http://localhost:8151/docs |
| MySQL | 3311 | 3306 | `localhost:3311` |
| MongoDB | 27101 | 27017 | `localhost:27101` |
| Redis | 6381 | 6379 | `localhost:6381` |
| Kafka (host clients) | 9091 | 9092 | `localhost:9091` |
| Kafka (containers) | — | 29092 | `kafka:29092` |

Ports live **only** in `.env`. To change one, edit `.env` (and `.env.example` if it's a team-wide change).
`./scripts/check-ports.sh` shows what is free. The scripts never stop other programs to free a port.

## Docker infrastructure

```bash
./scripts/infra.sh up          # start (detached)
./scripts/infra.sh status      # container status + health
./scripts/infra.sh logs kafka  # follow logs (omit name for all)
./scripts/infra.sh restart mysql
./scripts/infra.sh down        # stop; data volumes are KEPT
./scripts/infra.sh config      # validate docker-compose.yml
```

- Compose project `data260-group1`, containers `data260-g1-*`, network `data260-group1-net`,
  volumes `data260-group1_*`. None of this affects other Docker projects.
- MySQL and MongoDB init scripts in `database/` run **only on the first start of an empty volume**.
  To wipe this project's data and re-run them: `docker compose -p data260-group1 down -v`
  (deletes only this project's volumes. Be sure first).
- Kafka runs single-node KRaft (no ZooKeeper). `kafka-init` creates every topic in
  `shared/kafka/topics.txt` plus its `.dlq` topic, then exits with code 0.

## Backend

```bash
./scripts/start-service.sh booking-service    # foreground, auto-reload
./scripts/start-all-services.sh               # all six in background (.run/logs/)
./scripts/stop-all-services.sh                # stops only what start-all started
./scripts/health-check.sh                     # GET /health on all six
./scripts/health-check.sh --deps              # also probe MySQL/MongoDB/Redis/Kafka
```

Every service exposes:

| Endpoint | Meaning |
|---|---|
| `GET /` | service name, description, owner |
| `GET /health` | **process is up**. Does *not* check databases/Kafka (`"dependencies": "not_checked"`) |
| `GET /health/dependencies` | actively probes this service's dependencies. Returns 503 if any are down |
| `GET /docs`, `/redoc` | Swagger / ReDoc |

## Frontend

```bash
./scripts/start-frontend.sh            # dev server on :5101 (fails if 5101 is busy)
cd frontend && npm run build           # production build to frontend/dist
```

API base URLs come from `VITE_*_API_URL` in the root `.env`, read in one place:
`frontend/src/services/api.js`. Don't hardcode ports in components.

## Tests

```bash
./scripts/run-tests.sh                   # shared tests + every service
./scripts/run-tests.sh booking-service   # one service
./scripts/run-tests.sh --integration     # also test live MySQL/MongoDB/Redis/Kafka
```

## GitHub workflow (summary)

`main` (stable) ← `develop` (integration) ← `feature/<module>-<name>`.
Open PRs into `develop`; never push directly to `main`. Full guide: [docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md).

## Manual commands (no bash scripts)

```bash
cp .env.example .env          # then replace every change_me with a password
python3.12 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
docker compose -f infrastructure/docker-compose.yml --env-file .env up -d
cd backend/booking-service
PYTHONPATH=.:../.. ../../.venv/bin/uvicorn app.main:app --port 8121 --reload
cd frontend && npm install && npm run dev
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `.env not found` | `./scripts/setup-env.sh` |
| `Python environment missing` | `./scripts/setup-python.sh` |
| `Port 5101 is already in use` / service refuses to start | `./scripts/check-ports.sh`. Stop your own old process, or pick another free port ending in 1 in `.env` |
| `Docker is not running` | open Docker Desktop and wait for the whale icon to settle |
| `/health/dependencies` shows `down` | `./scripts/infra.sh status`. Wait for `(healthy)`, check `./scripts/infra.sh logs <svc>` |
| MySQL auth errors after changing `.env` passwords | the old password is stored in the volume. Change it back, or wipe with `down -v` |
| Kafka client can't connect from your laptop | use `localhost:9091`. From inside Docker use `kafka:29092` |
| `ModuleNotFoundError: shared` | start services via the scripts (they set `PYTHONPATH`) |
| `npm`/`node` not found | install Node 22 LTS, open a new terminal |
