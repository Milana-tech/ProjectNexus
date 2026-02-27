# Project Nexus — 5-Minute Demo Walkthrough

This script walks through the proof-of-concept from a cold start to live data in under 5 minutes.

---

## Step 1 — Start the full stack (30 seconds)

```bash
docker compose up --build
```

Expected output: 4 services start — `db`, `backend`, `frontend`, `simulator`.

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
```

Or open the frontend in a browser:

```
http://localhost:5173
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

## Step 7 — Show the modular algorithm registry (~15 seconds)

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
