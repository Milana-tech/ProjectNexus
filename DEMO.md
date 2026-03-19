# Project Nexus — 5-Minute Demo Walkthrough

This script walks through the proof-of-concept from a cold start to live data in under 5 minutes.

---

## Step 1 — Start the full stack (30 seconds)

```bash
# Option A (recommended): one-command demo start
./run.sh

# Option B (PowerShell)
./run.ps1

# Option C (manual)
docker compose up --build
```

Expected output: services start — `db`, `migrate`, `backend`, `backend_php`, `frontend`, `simulator`.

**What to point out:**
- Single command starts everything: TimescaleDB, FastAPI, React dashboard, and the data simulator.
- No manual setup or seeding required.

---

## Step 2 — Verify all services are healthy (~15 seconds)

Open a second terminal and run:

```bash
# API health
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# Database connectivity via API
curl http://localhost:8000/db
# Expected: {"ok":true,"now":"<current timestamp>"}

# PHP backend health (Symfony)
curl http://localhost:8001/health
# Expected: {"status":"ok"}
```

Or open the frontend in a browser:

```
http://localhost:3000
```

---

## Step 3 — Show the simulator bootstrapping demo data (~30 seconds)

```bash
docker logs project-nexus-simulator
```

**What to point out:**
- On first startup, the simulator created one **entity** ("Greenhouse A", type = greenhouse).
- It registered two **metrics** linked to that entity: `temperature` (°C) and `humidity` (%).
- It is now inserting a new reading every 5 seconds for each metric.
- The entity name, type, and metrics are all configurable via environment variables — not hardcoded.

---

## Step 4 — Show live readings accumulating in the database (~30 seconds)

```bash
docker exec project-nexus-db psql -U nexus -d nexus -c \
  "SELECT m.name AS metric, r.timestamp, r.value
   FROM readings r
   JOIN metrics m ON m.id = r.metric_id
   ORDER BY r.timestamp DESC
   LIMIT 10;"
```

**What to point out:**
- Raw time-series data stored in the `readings` table (TimescaleDB hypertable).
- Clean separation: readings contain only `metric_id`, `timestamp`, `value` — no anomaly fields mixed in.

---

## Step 5 — Show the generic data model (~30 seconds)

```bash
docker exec project-nexus-db psql -U nexus -d nexus -c \
  "SELECT e.name AS entity, e.type, m.name AS metric, m.unit
   FROM entities e
   JOIN metrics m ON m.entity_id = e.id;"
```

**What to point out:**
- `entities` is generic — type can be greenhouse, factory, lab, etc.
- `metrics` are linked to an entity and carry a unit.
- Swapping to a different domain requires only inserting a new entity row — no schema change.

---

## Step 6 — Show injected spikes (anomaly demo data) (~30 seconds)

```bash
docker exec project-nexus-db psql -U nexus -d nexus -c \
  "SELECT m.name AS metric, r.timestamp, r.value
   FROM readings r
   JOIN metrics m ON m.id = r.metric_id
   ORDER BY r.value DESC
   LIMIT 6;"
```

**What to point out:**
- Every 20 readings the simulator injects a spike (2–2.5× normal range).
- These are the anomalies the detection algorithm will target.
- Anomaly results will be stored separately in `anomaly_results`, linked to both the metric and the algorithm that detected it.

---

## Step 7 — Run anomaly detection (API call) (~30 seconds)

1) Pick a metric from the UI:

- Open `http://localhost:3000`
- Select an **Entity** and a **Metric**
- Note the metric id from the URL or use the API below

2) Get a metric id via API:

```bash
# Get entities (zones)
curl http://localhost:8000/entities

# Pick the first entity id, then list its metrics
curl "http://localhost:8000/metrics?entity_id=1"
```

3) Run anomalies for the last hour:

```bash
# Replace METRIC_ID with the id from /metrics
# Replace START_ISO / END_ISO with ISO-8601 timestamps (UTC recommended), e.g.
#   START_ISO=2026-03-17T01:00:00+00:00
#   END_ISO=2026-03-17T02:00:00+00:00
curl -X POST "http://localhost:8000/anomalies/run?metric_id=METRIC_ID&algorithm=zscore&start=START_ISO&end=END_ISO"
```

PowerShell helper to generate times (optional):

```powershell
$end = (Get-Date).ToUniversalTime().ToString("o")
$start = (Get-Date).ToUniversalTime().AddHours(-1).ToString("o")
curl -Method POST "http://localhost:8000/anomalies/run?metric_id=METRIC_ID&algorithm=zscore&start=$start&end=$end"
```

---

## Step 8 — Retrieve anomaly results (API call) (~15 seconds)

```bash
curl "http://localhost:8000/anomalies?metric_id=METRIC_ID&start=START_ISO&end=END_ISO"
```

PowerShell (optional):

```powershell
curl "http://localhost:8000/anomalies?metric_id=METRIC_ID&start=$start&end=$end"
```

Expected: a JSON array with `timestamp`, `score`, and `flag`.

---

## Step 9 — Show the modular algorithm registry (~15 seconds)

```bash
docker exec project-nexus-db psql -U nexus -d nexus -c \
  "SELECT * FROM algorithms;"
```

**What to point out:**
- The `algorithms` table is the registry for detection and forecasting methods.
- Each result in `anomaly_results` and `forecast_results` carries an `algorithm_id` — full traceability.
- Adding a new algorithm = inserting a row, not changing the schema.

---

## Clean up

```bash
# Stop containers but keep data
docker compose down

# Full reset (wipes database)
docker compose down -v
```

---

## Summary

| Feature | Status |
|---|---|
| Single-command start | ✅ `docker compose up --build` |
| Generic entity/metric model | ✅ Live |
| Live time-series ingestion | ✅ Simulator running |
| Spike injection for anomaly testing | ✅ Every 20 readings |
| Modular algorithm registry | ✅ Schema ready |
| Anomaly detection algorithm | 🔜 Next sprint |
| Dashboard visualisation | 🔜 Next sprint |
| Forecasting | 🔜 Next sprint (conditional) |
