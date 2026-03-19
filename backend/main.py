import os
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, field_validator, model_validator
from anomaly import ALGORITHMS, get_algorithm

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


def _parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 datetime string, accepting both Z and +00:00 suffixes."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def get_conn() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail={"error": "DATABASE_URL is not set", "field": None, "index": None})
    return psycopg.connect(database_url, row_factory=dict_row)


def _error_schema(message: str, field: str | None = None, index: int | None = None) -> dict:
    return {"error": message, "field": field, "index": index}


def _coerce_4xx_detail(detail: Any) -> dict:
    if isinstance(detail, dict) and set(detail.keys()) == {"error", "field", "index"}:
        return detail
    if isinstance(detail, str):
        return _error_schema(detail)
    return _error_schema("Request failed")


def _extract_field_index_from_loc(loc: tuple[Any, ...]) -> tuple[str | None, int | None]:
    if not loc:
        return None, None

    parts = list(loc)
    if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
        parts = parts[1:]

    index: int | None = None
    for i in range(len(parts) - 1):
        if isinstance(parts[i], str) and parts[i] in {"readings", "items"} and isinstance(parts[i + 1], int):
            index = parts[i + 1]
            break

    field = parts[-1] if parts and isinstance(parts[-1], str) else None
    return field, index


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and set(exc.detail.keys()) == {"error", "field", "index"}:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    if 400 <= exc.status_code <= 499:
        detail = _coerce_4xx_detail(exc.detail)
        return JSONResponse(status_code=exc.status_code, content=detail)

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if 400 <= exc.status_code <= 499:
        return JSONResponse(status_code=exc.status_code, content=_error_schema(exc.detail))
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else None
    if not first:
        return JSONResponse(status_code=400, content=_error_schema("Validation error"))

    loc = tuple(first.get("loc", ()))
    field, index = _extract_field_index_from_loc(loc)
    msg = first.get("msg") or "Validation error"
    return JSONResponse(status_code=400, content=_error_schema(str(msg), field=field, index=index))


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
        raise HTTPException(status_code=503, detail=_error_schema("DATABASE_URL is not set", field=None))
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT now();")
                (now,) = cur.fetchone()
        return {"ok": True, "now": str(now)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_schema(str(e), field=None))


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


# ---------------------------------------------------------------------------
# Algorithms
# ---------------------------------------------------------------------------

@app.get("/algorithms")
def get_algorithms():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM algorithms ORDER BY name;")
                rows = cur.fetchall()

        runtime_supported = set(ALGORITHMS.keys())
        available = [row["name"] for row in rows if row["name"] in runtime_supported]
        return [{"name": name, "label": name.title()} for name in available]
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to load algorithms")
        raise HTTPException(status_code=500, detail="Failed to load algorithms") from e


# ---------------------------------------------------------------------------
# Metrics — list metrics for a zone/entity (used by frontend metric selector)
# ---------------------------------------------------------------------------

@app.get("/metrics")
def get_metrics(entity_id: int = Query(..., gt=0, description="Zone/entity ID")):
    """Returns all metrics belonging to devices in the given zone."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM zones WHERE id = %s", (entity_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=_error_schema(f"Zone {entity_id} not found.", field="entity_id"))
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


# ---------------------------------------------------------------------------
# Models for bulk ingest
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
                    status_code=400,
                    detail=_error_schema(f"Unknown metric_id(s): {sorted(unknown)}.", field="metric_id"),
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
        raise HTTPException(status_code=400, detail=_error_schema(f"Invalid zone id: {zone_id}.", field="zone_id"))

    now_utc = datetime.now(timezone.utc)
    if start is None:
        start = now_utc - timedelta(hours=24)
    if end is None:
        end = now_utc

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    if start >= end:
        raise HTTPException(status_code=400, detail=_error_schema("start must be before end", field=None))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM zones WHERE id = %s", (zid,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=_error_schema(f"Zone {zid} not found", field="zone_id"))

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
        {"timestamp": row["timestamp"].isoformat(), "metric": row["metric"], "value": row["value"]}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /readings
# ---------------------------------------------------------------------------

@app.get("/readings")
def get_readings(
    metric_id: str = Query(..., description="Metric ID (numeric)"),
    start: str     = Query(None, description="Start datetime, ISO 8601"),
    end: str       = Query(None, description="End datetime, ISO 8601"),
    limit: int     = Query(500, ge=1, le=5000),
) -> dict:
    try:
        mid = int(metric_id)
        if mid <= 0:
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=400, detail=_error_schema(f"Invalid metric_id: '{metric_id}'. Expected a positive numeric id.", field="metric_id"))

    start_dt = None
    end_dt   = None
    if start:
        try:
            start_dt = _parse_iso(start)
        except ValueError:
            raise HTTPException(status_code=400, detail=_error_schema(f"Invalid start: '{start}'. Use ISO 8601 format.", field="start"))
    if end:
        try:
            end_dt = _parse_iso(end)
        except ValueError:
            raise HTTPException(status_code=400, detail=_error_schema(f"Invalid end: '{end}'. Use ISO 8601 format.", field="end"))

    if start_dt and end_dt and start_dt >= end_dt:
        raise HTTPException(status_code=400, detail=_error_schema("'start' must be before 'end'.", field=None))

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, unit FROM metrics WHERE id = %s", (mid,))
                metric = cur.fetchone()
                if not metric:
                    raise HTTPException(status_code=404, detail=_error_schema(f"metric_id '{mid}' not found.", field="metric_id"))

                conditions = ["metric_id = %s"]
                params: list = [mid]
                if start_dt:
                    conditions.append("timestamp >= %s")
                    params.append(start_dt)
                if end_dt:
                    conditions.append("timestamp <= %s")
                    params.append(end_dt)
                params.append(limit)

                cur.execute(
                    "SELECT id, metric_id, timestamp, value, created_at "
                    "FROM readings "
                    f"WHERE {' AND '.join(conditions)} "
                    "ORDER BY timestamp ASC LIMIT %s",
                    params,
                )
                rows = cur.fetchall()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {
        "metric": {"id": metric["id"], "name": metric["name"], "unit": metric["unit"]},
        "count": len(rows),
        "readings": [
            {"id": r["id"], "timestamp": r["timestamp"].isoformat(), "value": r["value"]}
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

@app.post("/anomalies/run")
def run_anomaly(
    metric_id: str = Query(..., description="Metric ID (numeric)"),
    algorithm: str = Query(..., description="Algorithm name, e.g. 'zscore'"),
    start: str     = Query(..., description="Start datetime, ISO 8601"),
    end: str       = Query(..., description="End datetime, ISO 8601"),
):
    try:
        fn = get_algorithm(algorithm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_error_schema(str(e), field="algorithm"))

    try:
        start_dt = _parse_iso(start)
    except ValueError:
        raise HTTPException(status_code=400, detail=_error_schema(f"Invalid start: '{start}'. Use ISO 8601 format.", field="start"))
    try:
        end_dt = _parse_iso(end)
    except ValueError:
        raise HTTPException(status_code=400, detail=_error_schema(f"Invalid end: '{end}'. Use ISO 8601 format.", field="end"))

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail=_error_schema("'start' must be before 'end'", field=None))

    try:
        mid = int(metric_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=_error_schema(f"Invalid metric_id: '{metric_id}'. Expected a numeric id.", field="metric_id"))

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM metrics WHERE id = %s", (mid,))
                if cur.fetchone() is None:
                    raise HTTPException(status_code=404, detail=_error_schema(f"metric_id '{mid}' not found.", field="metric_id"))

                cur.execute("SELECT id FROM algorithms WHERE name = %s", (algorithm,))
                algo_row = cur.fetchone()
                if algo_row is None:
                    raise HTTPException(status_code=400, detail=_error_schema(f"Algorithm '{algorithm}' not registered in algorithms table.", field="algorithm"))
                algorithm_id = algo_row["id"]

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
        return {"status": "done", "points_processed": 0}

    timestamps = [r["timestamp"] for r in rows]
    values     = [r["value"] for r in rows]
    results    = fn(values)

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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store results: {e}")

    return {"status": "done", "points_processed": len(results)}


@app.get("/anomalies")
async def get_anomalies(metric_id: str, start: str, end: str):
    try:
        start_dt = _parse_iso(start)
    except ValueError:
        raise HTTPException(status_code=400, detail=_error_schema(f"Invalid start: '{start}'. Use ISO 8601 format.", field="start"))
    try:
        end_dt = _parse_iso(end)
    except ValueError:
        raise HTTPException(status_code=400, detail=_error_schema(f"Invalid end: '{end}'. Use ISO 8601 format.", field="end"))

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail=_error_schema("'start' must be before 'end'", field=None))

    try:
        mid = int(metric_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=_error_schema(f"Invalid metric_id: '{metric_id}'. Expected a numeric id.", field="metric_id"))

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM metrics WHERE id = %s", (mid,))
                if cur.fetchone() is None:
                    raise HTTPException(status_code=404, detail=_error_schema(f"metric_id '{mid}' not found.", field="metric_id"))

                cur.execute("""
                    SELECT timestamp, anomaly_score, anomaly_flag
                    FROM anomaly_results
                    WHERE metric_id = %s
                    AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp ASC
                """, (mid, start_dt, end_dt))
                rows = cur.fetchall()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return [
        {
            "timestamp": r["timestamp"].isoformat(),
            "score": r["anomaly_score"],
            "flag": r["anomaly_flag"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Entry point (for local dev without Docker)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
