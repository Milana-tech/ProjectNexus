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


def get_conn() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not set")
    return psycopg.connect(database_url, row_factory=dict_row)


# ---------------------------------------------------------------------------
# Health / DB check
# ---------------------------------------------------------------------------

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
                cur.execute("SELECT id, name FROM zones ORDER BY name;")
                rows = cur.fetchall()
        return [{"id": row["id"], "name": row["name"]} for row in rows]
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# UI config
# ---------------------------------------------------------------------------

@app.get("/config")
def get_config():
    """Return UI configuration values so the frontend does not hardcode them."""
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
# POST /readings/bulk — ingest time-series readings (used by simulator)
# ---------------------------------------------------------------------------

@app.post(
    "/readings/bulk",
    response_model=BulkReadingsResponse,
    summary="Ingest a batch of time-series readings",
)
def bulk_ingest(body: BulkReadingsRequest) -> BulkReadingsResponse:
    """
    Accepts `{ readings: [{metric_id, timestamp, value}] }`.

    Validates:
    - All metric_ids exist in the DB (422 if any unknown)
    - Timestamps are not in the future
    - Values are finite numbers
    - List is non-empty and <= 1000 items

    Returns `{ inserted, errors }` — partial success is possible per row.
    """
    inserted = 0
    errors: list[dict] = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Validate all metric_ids and resolve zone_id via metric→device→zone
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
                    detail=(
                        f"Unknown metric_id(s): {sorted(unknown)}. "
                        "Register the metric before sending readings."
                    ),
                )

            now = datetime.now(timezone.utc)
            for idx, reading in enumerate(body.readings):
                try:
                    cur.execute(
                        """
                        INSERT INTO readings (metric_id, zone_id, timestamp, value, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            reading.metric_id,
                            metric_zone_map[reading.metric_id],
                            reading.timestamp,
                            reading.value,
                            now,
                        ),
                    )
                    inserted += 1
                except Exception as exc:
                    errors.append({"index": idx, "error": str(exc)})
                    conn.rollback()

            conn.commit()

    log.info("Bulk ingest complete: inserted=%d errors=%d", inserted, len(errors))
    return BulkReadingsResponse(inserted=inserted, errors=errors)


# ---------------------------------------------------------------------------
# GET /readings/{zone_id} — zone-based query (used by frontend)
# ---------------------------------------------------------------------------

@app.get("/readings/{zone_id}", summary="Query readings for a zone")
def get_readings_by_zone(
    zone_id: str = Path(..., description="Zone ID (numeric)"),
    start: Optional[datetime] = Query(None, description="Start datetime (ISO 8601)"),
    end: Optional[datetime] = Query(None, description="End datetime (ISO 8601)"),
) -> list[dict[str, Any]]:
    """
    Returns readings for all metrics in a zone, ordered by timestamp ascending.
    Defaults to the last 24 hours if no range is provided.
    """
    try:
        zid = int(zone_id)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid zone id: {zone_id}. Expected numeric id.")

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
        raise HTTPException(
            status_code=400,
            detail=f"start ({start.isoformat()}) must be before end ({end.isoformat()})",
        )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM zones WHERE id = %s", (zid,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"Zone {zid} not found")

            cur.execute(
                """
                SELECT r.timestamp, m.name AS metric, r.value
                FROM readings r
                JOIN metrics m ON m.id = r.metric_id
                WHERE r.zone_id = %s
                  AND r.timestamp BETWEEN %s AND %s
                ORDER BY r.timestamp ASC
                """,
                (zid, start, end),
            )
            rows = cur.fetchall()

    return [
        {
            "timestamp": row["timestamp"].isoformat(),
            "metric": row["metric"],
            "value": row["value"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /readings — metric-based query (used by API consumers / tests)
# ---------------------------------------------------------------------------

@app.get("/readings", summary="Query time-series readings by metric")
def get_readings(
    metric_id: int = Query(..., gt=0, description="Metric to query"),
    start: Optional[datetime] = Query(None, description="Start timestamp, inclusive (ISO-8601)"),
    end: Optional[datetime] = Query(None, description="End timestamp, inclusive (ISO-8601)"),
    limit: int = Query(500, ge=1, le=5000, description="Max rows (default 500)"),
) -> dict:
    """
    Returns readings for a metric, ordered newest-first.

    - `metric_id` is required
    - `start` / `end` are optional time-window filters
    - `limit` caps result size (max 5000)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, unit FROM metrics WHERE id = %s", (metric_id,))
            metric = cur.fetchone()
            if not metric:
                raise HTTPException(status_code=404, detail=f"metric_id {metric_id} not found.")

            if start and start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end and end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            if start and end and end < start:
                raise HTTPException(status_code=422, detail="'end' must not be before 'start'.")

            conditions = ["metric_id = %s"]
            params: list = [metric_id]
            if start:
                conditions.append("timestamp >= %s")
                params.append(start)
            if end:
                conditions.append("timestamp <= %s")
                params.append(end)
            params.append(limit)

            cur.execute(
                "SELECT id, metric_id, timestamp, value, created_at "
                "FROM readings "
                f"WHERE {' AND '.join(conditions)} "
                "ORDER BY timestamp DESC "
                "LIMIT %s",
                params,
            )
            rows = cur.fetchall()

    return {
        "metric": {"id": metric["id"], "name": metric["name"], "unit": metric["unit"]},
        "count": len(rows),
        "readings": [
            {"id": r["id"], "timestamp": r["timestamp"].isoformat(), "value": r["value"]}
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Entry point (for local dev without Docker)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)