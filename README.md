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

This starts all services in one command:
- **Database** on `localhost:5432`
- **API** on `http://localhost:8000`
- **Frontend** on `http://localhost:3000`
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
| `SIM_ZONE_NAME` | `Zone 1` | Name of the demo zone |
| `SIM_DEVICE_NAME` | `Greenhouse A` | Name of the demo device |
| `SIM_DEVICE_TYPE` | `greenhouse` | Type of the demo device |
| `SIM_METRICS` | `temperature,humidity` | Comma-separated metric names |
| `SIM_INTERVAL_SECONDS` | `5` | Seconds between reading inserts |
| `SIM_SPIKE_EVERY` | `20` | Inject an anomalous spike every N readings |

## API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health check |
| `/db` | GET | Database connectivity check |
| `/zones` | GET | List all zones |
| `/config` | GET | UI configuration (title, time ranges) |
| `/readings/{zone_id}` | GET | Zone readings with optional `start`/`end` filters |
| `/readings` | GET | Metric readings with optional filters |
| `/readings/bulk` | POST | Ingest a batch of readings (used by simulator) |

## Demo

See [DEMO.md](DEMO.md) for a structured 5-minute walkthrough of the full PoC.

## Useful DB commands

```bash
# Connect to DB
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB

# Show tables
SELECT table_name FROM information_schema.tables WHERE table_schema='public';

# List zones
SELECT id, name FROM zones ORDER BY id;

# Recent readings
SELECT * FROM readings ORDER BY timestamp DESC LIMIT 10;
```
