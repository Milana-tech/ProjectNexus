"""
Project Nexus — Data Simulator

Ensures demo entity + metrics exist, then continuously inserts readings.
Every SIM_SPIKE_EVERY iterations it injects an obvious spike so the
anomaly detection algorithm has something to find.

Configuration (all via environment variables):
  DATABASE_URL         Postgres connection string (required)
  SIM_ENTITY_NAME      Name of the demo entity          (default: Greenhouse A)
  SIM_ENTITY_TYPE      Type of the demo entity          (default: greenhouse)
  SIM_METRICS          Comma-separated metric names     (default: temperature,humidity)
  SIM_INTERVAL_SECONDS Seconds between readings         (default: 5)
  SIM_SPIKE_EVERY      Insert a spike every N readings  (default: 20)
"""

import os
import random
import time
import logging
from datetime import datetime, timezone

import psycopg
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [simulator] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

API_BASE_URL = os.getenv("API_BASE_URL", "http://backend:8000")
ENTITY_NAME  = os.getenv("SIM_ENTITY_NAME", "Greenhouse A")
ENTITY_TYPE  = os.getenv("SIM_ENTITY_TYPE", "greenhouse")
METRIC_NAMES = [m.strip() for m in os.getenv("SIM_METRICS", "temperature,humidity").split(",") if m.strip()]
INTERVAL     = float(os.getenv("SIM_INTERVAL_SECONDS", "5"))
SPIKE_EVERY  = int(os.getenv("SIM_SPIKE_EVERY", "20"))

# Realistic baseline ranges per metric (min, max, spike_multiplier)
METRIC_PROFILES: dict[str, tuple[float, float, float]] = {
    "temperature": (18.0, 26.0, 2.5),
    "humidity":    (40.0, 70.0, 2.0),
}
DEFAULT_PROFILE = (0.0, 100.0, 3.0)


def normal_value(metric: str) -> float:
    lo, hi, _ = METRIC_PROFILES.get(metric, DEFAULT_PROFILE)
    return round(random.uniform(lo, hi), 2)


def spike_value(metric: str) -> float:
    lo, hi, mult = METRIC_PROFILES.get(metric, DEFAULT_PROFILE)
    return round(random.uniform(lo, hi) * mult, 2)


def _default_unit(metric: str) -> str:
    return {"temperature": "°C", "humidity": "%", "pressure": "hPa", "co2": "ppm"}.get(metric, "")


# ---------------------------------------------------------------------------
# DB bootstrap — wait for Postgres, create entity + metrics if needed
# (Direct DB access only during startup; all readings go through the API)
# ---------------------------------------------------------------------------

def wait_for_db(retries: int = 20, delay: float = 3.0) -> psycopg.Connection:
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg.connect(DATABASE_URL)
            log.info("Connected to database.")
            return conn
        except Exception as exc:
            log.warning("DB not ready (attempt %d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError("Could not connect to database after %d attempts." % retries)


def bootstrap(conn: psycopg.Connection) -> dict[str, int]:
    """
    Ensure the entity and all metrics exist.
    Returns {metric_name: metric_id}.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO entities (name, type) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (ENTITY_NAME, ENTITY_TYPE),
        )
        cur.execute("SELECT id FROM entities WHERE name = %s", (ENTITY_NAME,))
        (entity_id,) = cur.fetchone()
        log.info("Entity '%s' (type=%s) id=%d", ENTITY_NAME, ENTITY_TYPE, entity_id)

        metric_ids: dict[str, int] = {}
        for metric_name in METRIC_NAMES:
            cur.execute(
                """
                INSERT INTO metrics (entity_id, name, unit)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (entity_id, metric_name, _default_unit(metric_name)),
            )
            cur.execute(
                "SELECT id FROM metrics WHERE entity_id = %s AND name = %s",
                (entity_id, metric_name),
            )
            (metric_id,) = cur.fetchone()
            metric_ids[metric_name] = metric_id
            log.info("  Metric '%s' id=%d", metric_name, metric_id)

        conn.commit()
    return metric_ids


# ---------------------------------------------------------------------------
# Wait for API to be ready
# ---------------------------------------------------------------------------

def wait_for_api(retries: int = 20, delay: float = 3.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            r = httpx.get(f"{API_BASE_URL}/health", timeout=5)
            if r.status_code == 200:
                log.info("API is ready at %s", API_BASE_URL)
                return
        except Exception as exc:
            log.warning("API not ready (attempt %d/%d): %s", attempt, retries, exc)
        time.sleep(delay)
    raise RuntimeError("API did not become ready after %d attempts." % retries)


# ---------------------------------------------------------------------------
# Post readings to the bulk API
# ---------------------------------------------------------------------------

def post_readings(readings: list[dict]) -> None:
    try:
        r = httpx.post(f"{API_BASE_URL}/readings/bulk", json={"readings": readings}, timeout=10)
        if r.status_code == 200:
            body = r.json()
            log.info("API accepted: inserted=%d errors=%d", body["inserted"], len(body["errors"]))
            for err in body["errors"]:
                log.error("  Row error: %s", err)
        else:
            log.error("API rejected batch: status=%d body=%s", r.status_code, r.text[:300])
    except Exception as exc:
        log.error("Failed to POST readings: %s", exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_loop(metric_ids: dict[str, int]) -> None:
    iteration = 0
    log.info(
        "Starting insert loop — interval=%ss, spike every %s readings",
        INTERVAL, SPIKE_EVERY,
    )
    while True:
        iteration += 1
        is_spike = (iteration % SPIKE_EVERY == 0)
        now = datetime.now(timezone.utc).isoformat()

        batch: list[dict] = []
        for metric_name, metric_id in metric_ids.items():
            value = spike_value(metric_name) if is_spike else normal_value(metric_name)
            batch.append({"metric_id": metric_id, "timestamp": now, "value": value})
            log.log(
                logging.WARNING if is_spike else logging.INFO,
                "%s  iter=%-4d  metric=%-15s  value=%s",
                "SPIKE " if is_spike else "normal",
                iteration, metric_name, value,
            )

        post_readings(batch)
        time.sleep(INTERVAL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info("Project Nexus simulator starting...")
    log.info(
        "Config: entity='%s' type='%s' metrics=%s interval=%ss spike_every=%s api=%s",
        ENTITY_NAME, ENTITY_TYPE, METRIC_NAMES, INTERVAL, SPIKE_EVERY, API_BASE_URL,
    )

    conn = wait_for_db()
    metric_ids = bootstrap(conn)
    conn.close()  # DB only needed for bootstrap; readings go via API

    wait_for_api()
    run_loop(metric_ids)