# Project Nexus

Proof-of-concept anomaly detection system for time-series data.
Stores measurements in a generic format, detects anomalies using statistical methods,
and visualises results through a basic dashboard.

## Stack

| Service | Description |
|---|---|
| `db` | TimescaleDB (PostgreSQL) — time-series storage |
| `backend` | FastAPI — REST ingestion + anomaly detection API |
| `frontend` | React + Vite — dashboard |
| `simulator` | Python — continuously inserts fake readings for demo/testing |

## Getting started

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### 1. Configure environment

```bash
cp .env.example .env
```

The defaults work out of the box. Edit `.env` to customise the simulator entity/metrics.

### 2. Start the full stack

```bash
docker compose up --build
```

This starts all four services in one command:
- **Database** on `localhost:5432`
- **API** on `http://localhost:8000`
- **Frontend** on `http://localhost:5173`
- **Simulator** — inserts a reading every 5 seconds; injects a spike every 20 readings

### 3. Stop and clean up

```bash
# Stop containers (keeps data)
docker compose down

# Stop and wipe database volume (fresh start)
docker compose down -v
```

## Simulator configuration

All settings are in `.env`:

| Variable | Default | Description |
|---|---|---|
| `SIM_ENTITY_NAME` | `Greenhouse A` | Name of the demo entity |
| `SIM_ENTITY_TYPE` | `greenhouse` | Type of the demo entity |
| `SIM_METRICS` | `temperature,humidity` | Comma-separated metric names |
| `SIM_INTERVAL_SECONDS` | `5` | Seconds between reading inserts |
| `SIM_SPIKE_EVERY` | `20` | Inject an anomalous spike every N readings |

## API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health check |
| `/db` | GET | Database connectivity check |

## Running (DB notes)

This repo uses an ERD-style schema in `backend/db/init.sql` (entities, metrics, measurements).
The development `init.sql` also contains compatibility shims so older code expecting
`zones`, `devices` and `readings` will continue to work.

Recommended ways to run locally:

- Fresh start (recommended for development):

```bash
docker compose down -v
docker compose up --build -d
```

- Patch a running DB (non-destructive) — applies the compatibility view/trigger and a
	generated `device_id` column so legacy `INSERT INTO readings` and joins work:

```bash
docker compose exec -T db psql -U nexus_dev -d projectnexus -c "ALTER TABLE metrics ADD COLUMN IF NOT EXISTS device_id BIGINT GENERATED ALWAYS AS (entity_id) STORED;"
docker compose exec -T db psql -U nexus_dev -d projectnexus -f backend/db/init.sql -v ON_ERROR_STOP=1
```

Note: the second command reads `backend/db/init.sql` which is idempotent and includes
the compatibility view/trigger. If you prefer, recreate the DB with the first `down -v` flow.

PHP runtime notes (after code changes): clear the Symfony cache and restart the container:

```bash
docker compose exec backend_php php /app/bin/console cache:clear --env=dev
docker compose restart backend_php
```

Quick simulator bootstrap (verifies entities/metrics exist):

```bash
docker compose exec -T simulator python -c "from simulator import wait_for_db, bootstrap; conn=wait_for_db(); print(bootstrap(conn)); conn.close()"
```

For troubleshooting, do:
`docker compose logs --no-color --since 1m backend_php`
