import os
import logging
import math
from datetime import datetime, timezone
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query
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
# Existing endpoints (preserved)
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db")
def db_check():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return {"ok": False, "error": "DATABASE_URL is not set"}

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT now();")
            (now,) = cur.fetchone()

    return {"ok": True, "now": str(now)}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

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
# POST /readings/bulk — ingest time-series readings
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
# GET /readings — universal time-series query
# ---------------------------------------------------------------------------

@app.get("/readings", summary="Query time-series readings")
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