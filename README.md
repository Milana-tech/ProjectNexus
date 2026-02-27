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

## Demo

See [DEMO.md](DEMO.md) for a structured 5-minute walkthrough of the full PoC.
