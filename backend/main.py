import os
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, model_validator
from anomaly import get_algorithm
from repositories import MeasurementRepository, AnomalyRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [api] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

app = FastAPI(title="Project Nexus API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Error handling middleware
# ---------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    log.warning("HTTP %s: %s", exc.status_code, exc.detail)
    return {"error": {"status_code": exc.status_code, "detail": exc.detail}}

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    log.exception("Unhandled exception")
    return {"error": {"status_code": 500, "detail": "Internal server error"}}

# ---------------------------------------------------------------------------
# Health / DB check
# ---------------------------------------------------------------------------

def get_conn() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not set")
    return psycopg.connect(database_url, row_factory=dict_row)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db")
def db_check():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return {"ok": False, "error": "DATABASE_URL is not set"}
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT now();")
                (now,) = cur.fetchone()
        return {"ok": True, "now": str(now)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------

@app.get("/zones")
def get_zones():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT id, name
                    FROM zones
                    ORDER BY name;
                """)
                rows = cur.fetchall()
        return [{"id": row["id"], "name": row["name"]} for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to load zones")
        raise HTTPException(status_code=500, detail="Failed to load zones") from e


# ---------------------------------------------------------------------------
# Entities  (domain-agnostic alias for /zones — used by the frontend dropdown)
# ---------------------------------------------------------------------------

@app.get("/entities", summary="List all entities")
def get_entities():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM zones ORDER BY name;")
                rows = cur.fetchall()
        return [{"id": row["id"], "name": row["name"]} for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to load entities")
        raise HTTPException(status_code=500, detail="Failed to load entities") from e

# ---------------------------------------------------------------------------
# UI config
# ---------------------------------------------------------------------------

@app.get("/config")
def get_config():
    return {
        "app_title": "Project Nexus — Environmental Dashboard",
        "quick_ranges": [
            {"label": "Last hour", "ms": 60 * 60 * 1000},
            {"label": "Last 6 h", "ms": 6 * 60 * 60 * 1000},
            {"label": "Last day", "ms": 24 * 60 * 60 * 1000},
            {"label": "Last week", "ms": 7 * 24 * 60 * 60 * 1000},
        ],
        "default_range_index": 1,
    }

# Metrics — list metrics for a zone/entity (used by frontend metric selector)

@app.get("/metrics")
def get_metrics(entity_id: int = Query(..., gt=0, description="Zone/entity ID")):
    """Returns all metrics belonging to devices in the given zone."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM zones WHERE id = %s", (entity_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"Zone {entity_id} not found.")
            cur.execute(
                """
                SELECT m.id, m.name, m.unit
                FROM metrics m
                JOIN devices d ON d.id = m.device_id
                WHERE d.zone_id = %s
                ORDER BY m.name
                """,
                (entity_id,),
            )
            rows = cur.fetchall()
    return [{"id": row["id"], "name": row["name"], "unit": row["unit"] or ""} for row in rows]

# Models for bulk ingest

class Reading(BaseModel):
    metric_id: int
    timestamp: datetime
    value: float

    @field_validator("metric_id")
    @classmethod
    def metric_id_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("metric_id must be a positive integer")
        return v

    @field_validator("timestamp")
    @classmethod
    def timestamp_not_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v > datetime.now(timezone.utc):
            raise ValueError(f"timestamp cannot be in the future: {v.isoformat()}")
        return v

    @field_validator("value")
    @classmethod
    def value_is_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("value must be a finite number")
        return v


class BulkReadingsRequest(BaseModel):
    readings: list[Reading]

    @model_validator(mode="after")
    def non_empty(self) -> "BulkReadingsRequest":
        if not self.readings:
            raise ValueError("readings list must contain at least one item")
        if len(self.readings) > 1000:
            raise ValueError("readings list cannot exceed 1000 items per request")
        return self


class BulkReadingsResponse(BaseModel):
    inserted: int
    errors: list[dict]


# ---------------------------------------------------------------------------
# POST /readings/bulk
# ---------------------------------------------------------------------------

@app.post("/readings/bulk", response_model=BulkReadingsResponse)
def bulk_ingest(body: BulkReadingsRequest) -> BulkReadingsResponse:
    inserted = 0
    errors: list[dict] = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            unique_ids = list({r.metric_id for r in body.readings})
            cur.execute(
                """
                SELECT m.id AS metric_id, d.zone_id
                FROM metrics m
                JOIN devices d ON d.id = m.device_id
                WHERE m.id = ANY(%s)
                """,
                (unique_ids,),
            )
            metric_zone_map = {row["metric_id"]: row["zone_id"] for row in cur.fetchall()}
            unknown = set(unique_ids) - set(metric_zone_map)
            if unknown:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown metric_id(s): {sorted(unknown)}.",
                )

            now = datetime.now(timezone.utc)
            for idx, reading in enumerate(body.readings):
                try:
                    cur.execute(
                        """
                        INSERT INTO readings (metric_id, zone_id, timestamp, value, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (reading.metric_id, metric_zone_map[reading.metric_id],
                        reading.timestamp, reading.value, now),
                    )
                    inserted += 1
                except Exception as exc:
                    errors.append({"index": idx, "error": str(exc)})
                    conn.rollback()

            conn.commit()

    log.info("Bulk ingest complete: inserted=%d errors=%d", inserted, len(errors))
    return BulkReadingsResponse(inserted=inserted, errors=errors)


# ---------------------------------------------------------------------------
# GET /readings/{zone_id}
# ---------------------------------------------------------------------------

@app.get("/readings/{zone_id}")
def get_readings_by_zone(
    zone_id: str = Path(..., description="Zone ID (numeric)"),
    start: Optional[datetime] = Query(None, description="Start datetime (ISO 8601)"),
    end: Optional[datetime] = Query(None, description="End datetime (ISO 8601)"),
) -> list[dict[str, Any]]:
    try:
        zid = int(zone_id)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid zone id: {zone_id}.")

    now_utc = datetime.now(timezone.utc)
    if start is None:
        start = now_utc - timedelta(hours=24)
    if end is None:
        end = now_utc

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    if start > end:
        raise HTTPException(status_code=400, detail="start must be before end")

    with get_conn() as conn:
        measurement_repo = MeasurementRepository(conn)
        rows = measurement_repo.get_readings_by_zone(zid, start, end)

    return [
        {"timestamp": row["timestamp"].isoformat(), "metric": row["metric"], "value": row["value"]}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /readings
# ---------------------------------------------------------------------------

@app.get("/readings", summary="Retrieve readings for a metric", description="Returns time-series readings for the specified metric, optionally filtered by date range.")
def get_readings(
    metric_id: int = Query(..., gt=0, description="Metric ID (numeric)"),
    start: str     = Query(None, description="Start datetime, ISO 8601 (optional)"),
    end: str       = Query(None, description="End datetime, ISO 8601 (optional)"),
    limit: int = Query(500, ge=1, le=5000, description="Maximum number of readings to return (1-5000)"),
) -> dict:
    # Validate start/end as strings so return 400 not 422
    start_dt = None
    end_dt = None
    if start:
        try:
            start_dt = datetime.fromisoformat(start)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid start: '{start}'. Use ISO 8601 format.")
    if end:
        try:
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid end: '{end}'. Use ISO 8601 format.")

    if start_dt and end_dt and start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="'start' must be before 'end'")

    with get_conn() as conn:
        measurement_repo = MeasurementRepository(conn)
        metric = measurement_repo.get_metric_by_id(metric_id)
        if not metric:
            raise HTTPException(status_code=404, detail=f"metric_id {metric_id} not found.")

        rows = measurement_repo.get_readings_with_anomalies(metric_id, start_dt, end_dt, limit)

    return {
        "metric": {"id": metric["id"], "name": metric["name"], "unit": metric["unit"]},
        "count": len(rows),
        "readings": [
            {"id": r["id"], "timestamp": r["timestamp"].isoformat(), "value": r["value"], "is_anomaly": r["is_anomaly"]}
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# GET /anomalies
# ---------------------------------------------------------------------------

@app.get("/anomalies", summary="Retrieve anomaly results for a metric", description="Returns anomaly detection results for the specified metric, optionally filtered by date range.")
def get_anomalies(
    metric_id: int = Query(..., gt=0, description="Metric ID (numeric)"),
    start: str     = Query(None, description="Start datetime, ISO 8601 (optional)"),
    end: str       = Query(None, description="End datetime, ISO 8601 (optional)"),
    limit: int = Query(500, ge=1, le=5000, description="Maximum number of results to return (1-5000)"),
) -> dict:
    # Validate start/end as strings so return 400 not 422
    start_dt = None
    end_dt = None
    if start:
        try:
            start_dt = datetime.fromisoformat(start)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid start: '{start}'. Use ISO 8601 format.")
    if end:
        try:
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid end: '{end}'. Use ISO 8601 format.")

    if start_dt and end_dt and start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="'start' must be before 'end'")

    with get_conn() as conn:
        anomaly_repo = AnomalyRepository(conn)
        metric = anomaly_repo.get_metric_by_id(metric_id)
        if not metric:
            raise HTTPException(status_code=404, detail=f"metric_id {metric_id} not found.")

        rows = anomaly_repo.get_anomalies(metric_id, start_dt, end_dt, limit)

    return {
        "metric": {"id": metric["id"], "name": metric["name"], "unit": metric["unit"]},
        "count": len(rows),
        "anomalies": [
            {"timestamp": row["timestamp"].isoformat(), "anomaly_score": row["anomaly_score"], "anomaly_flag": row["anomaly_flag"], "metadata": row["metadata"]}
            for row in rows
        ],
    }

# Anomaly detection
# ---------------------------------------------------------------------------

@app.post("/anomalies/run")
def run_anomaly(
    metric_id: str = Query(..., description="Metric ID (numeric)"),
    algorithm: str = Query(..., description="Algorithm name, e.g. 'zscore'"),
    start: str     = Query(..., description="Start datetime, ISO 8601"),
    end: str       = Query(..., description="End datetime, ISO 8601"),
):
    # Validate algorithm exists in registry
    try:
        fn = get_algorithm(algorithm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate start/end as strings → return 400 not 422
    try:
        start_dt = datetime.fromisoformat(start)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid start: '{start}'. Use ISO 8601 format.")
    try:
        end_dt = datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid end: '{end}'. Use ISO 8601 format.")

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="'start' must be before 'end'")

    # Validate metric_id is numeric
    try:
        mid = int(metric_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid metric_id: '{metric_id}'. Expected a numeric id.")

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Check metric exists
                cur.execute("SELECT id FROM metrics WHERE id = %s", (mid,))
                if cur.fetchone() is None:
                    raise HTTPException(status_code=404, detail=f"metric_id '{mid}' not found.")

                # Look up algorithm_id FK from algorithms table
                cur.execute("SELECT id FROM algorithms WHERE name = %s", (algorithm,))
                algo_row = cur.fetchone()
                if algo_row is None:
                    raise HTTPException(status_code=400, detail=f"Algorithm '{algorithm}' not registered in algorithms table.")
                algorithm_id = algo_row[0]  # Fix: Use algo_row[0] instead of algo_row["id"]

                # Fetch readings from correct table
                cur.execute("""
                    SELECT timestamp, value
                    FROM readings
                    WHERE metric_id = %s
                    AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp
                """, (mid, start_dt, end_dt))
                rows = cur.fetchall()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No readings found for metric_id '{mid}' in the given time range."
        )

    timestamps = [r["timestamp"] for r in rows]
    values     = [r["value"] for r in rows]
    results    = fn(values)

    # Store results and clear old ones first to avoid duplicates
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM anomaly_results WHERE metric_id = %s AND algorithm_id = %s",
                    (mid, algorithm_id)
                )
                for i, r in enumerate(results):
                    cur.execute("""
                        INSERT INTO anomaly_results
                        (metric_id, algorithm_id, timestamp, anomaly_score, anomaly_flag)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (mid, algorithm_id, timestamps[i], r["score"], r["flag"]))
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store results: {e}")

    return {"status": "done", "points_processed": len(results)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)