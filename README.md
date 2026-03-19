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

## Performance test (ingest)

A quick performance test script is included to validate bulk ingest behaviour.

- Script: [scripts/perf_ingest_test.py](scripts/perf_ingest_test.py)

Prerequisites:

1. Start the stack with Docker Compose so services are available:

```bash
docker compose up --build -d
```

2. Ensure the simulator has run once (it bootstraps demo `zones` and `metrics`) or run the simulator bootstrap manually.

Run the test (from repository root):

```bash
python scripts/perf_ingest_test.py
```

What the test does:

- Posts 500 valid readings in a single request to the PHP `/ingest` endpoint (via `http://localhost:8001/ingest`).
- Measures end-to-end elapsed time and checks it completes within 5s.
- Samples the `project-nexus-backend-php` container memory before and after the request and flags large memory growth.

If you want CI integration or different thresholds, tell me and I will add a pytest wrapper for this script.

## Ingest behaviour

The PHP ingestion endpoint performs strict pre-flight validation before persisting readings:

- It verifies that each `entity_id` (zone) and `metric_id` exists in the master tables and rejects the request with HTTP 400 if any ID is missing. The error response lists which `entity_id` or `metric_id` values were not found.
- The validation is implemented with an optimized query that minimizes database round-trips to keep validation latency low.
- Valid payloads are mapped to the internal readings model and inserted into the `readings` table using a single multi-row `INSERT` inside a transaction.
- Database connection or insert failures return HTTP 500 with a generic error message (no raw DB driver output is exposed to the client).

Relevant implementation:

- Ingest controller: [backend-php/src/Controller/IngestController.php](backend-php/src/Controller/IngestController.php#L1-L200)
- Quick validation script: [scripts/test_ingest_check.py](scripts/test_ingest_check.py#L1-L200)

If you want me to run a latency measurement for the pre-flight validation (to confirm it stays under 50ms) I can run the test and report back.
