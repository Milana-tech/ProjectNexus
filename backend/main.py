import os
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator, model_validator
from anomaly import get_algorithm
from repositories.measurement_repository import MeasurementRepository
from repositories.anomaly_repository import AnomalyRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [api] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

app = FastAPI(
    title="Project Nexus API",
    description="REST API for ingesting sensor readings and retrieving measurements/anomalies.",
    version="1.0.0",
)

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


def _parse_iso_datetime_or_400(raw_value: str, field_name: str) -> datetime:
    value = raw_value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}. Use ISO 8601 datetime.",
        ) from exc

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _build_error_payload(status_code: int, message: str, path: str) -> dict[str, Any]:
    return {
        "error": {
            "status": status_code,
            "message": message,
            "path": path,
        }
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        message = str(detail.get("message", detail))
    else:
        message = str(detail)

    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_payload(exc.status_code, message, request.url.path),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else None
    if first and "msg" in first:
        message = str(first["msg"])
    else:
        message = "Request validation failed"

    return JSONResponse(
        status_code=422,
        content=_build_error_payload(422, message, request.url.path),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on path %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=_build_error_payload(500, "Internal server error", request.url.path),
    )


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except HTTPException as exc:
        return await http_exception_handler(request, exc)
    except RequestValidationError as exc:
        return await request_validation_exception_handler(request, exc)
    except Exception as exc:
        return await generic_exception_handler(request, exc)


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


class ErrorDetailResponse(BaseModel):
    status: int
    message: str
    path: str


class ErrorResponse(BaseModel):
    error: ErrorDetailResponse


class MeasurementResponseItem(BaseModel):
    timestamp: datetime
    value: float
    metric_id: int


class ZoneReadingResponseItem(BaseModel):
    timestamp: datetime
    metric: str
    value: float


class AnomalyResponseItem(BaseModel):
    timestamp: datetime
    score: float | None
    flag: bool


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

@app.get(
    "/readings/{zone_id}",
    summary="List readings for a zone",
    description="Returns readings for all metrics in a zone within a time window.",
    response_model=list[ZoneReadingResponseItem],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
        404: {"model": ErrorResponse, "description": "Zone not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
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
        repo = MeasurementRepository(conn)
        if not repo.zone_exists(zid):
            raise HTTPException(status_code=404, detail=f"Zone {zid} not found")

        rows = repo.list_by_zone_and_range(zid, start, end)

    return [
        {"timestamp": row["timestamp"], "metric": row["metric"], "value": row["value"]}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /readings
# ---------------------------------------------------------------------------

@app.get(
    "/readings",
    summary="List measurements for one metric in a time range",
    description=(
        "Returns metric readings filtered by metric_id and time interval. "
        "Results are sorted chronologically ascending."
    ),
    response_model=list[MeasurementResponseItem],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid timestamps or missing parameters"},
        404: {"model": ErrorResponse, "description": "Metric not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_readings(
    metric_id: int = Query(..., gt=0, description="Metric identifier"),
    start_time: Optional[str] = Query(None, description="Start timestamp (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="End timestamp (ISO 8601)"),
    # Backward-compatible aliases for existing frontend clients.
    start: Optional[str] = Query(None, include_in_schema=False),
    end: Optional[str] = Query(None, include_in_schema=False),
    limit: int = Query(2000, ge=1, le=10000, description="Maximum rows to return (safe cap 10000)"),
) -> list[dict[str, Any]]:
    start_raw = start_time if start_time is not None else start
    end_raw = end_time if end_time is not None else end

    if not start_raw or not end_raw:
        raise HTTPException(
            status_code=400,
            detail="Both start_time and end_time query parameters are required.",
        )

    start_dt = _parse_iso_datetime_or_400(start_raw, "start_time")
    end_dt = _parse_iso_datetime_or_400(end_raw, "end_time")

    if end_dt < start_dt:
        raise HTTPException(status_code=400, detail="end_time must be after or equal to start_time.")

    with get_conn() as conn:
        repo = MeasurementRepository(conn)
        if not repo.metric_exists(metric_id):
            raise HTTPException(status_code=404, detail=f"metric_id {metric_id} not found.")
        rows = repo.list_by_metric_and_range(metric_id, start_dt, end_dt, limit)

    return [
        {
            "timestamp": r["timestamp"],
            "value": r["value"],
            "metric_id": r["metric_id"],
        }
        for r in rows
    ]


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
    # Validate algorithm exists in registry
    try:
        fn = get_algorithm(algorithm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate start/end as strings → return 400 not 422
    start_dt = _parse_iso_datetime_or_400(start, "start")
    end_dt = _parse_iso_datetime_or_400(end, "end")

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="'start' must be before 'end'")

    # Validate metric_id is numeric
    try:
        mid = int(metric_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid metric_id: '{metric_id}'. Expected a numeric id.")

    try:
        with get_conn() as conn:
            repo = AnomalyRepository(conn)

            if not repo.metric_exists(mid):
                raise HTTPException(status_code=404, detail=f"metric_id '{mid}' not found.")

            algorithm_id = repo.get_algorithm_id(algorithm)
            if algorithm_id is None:
                raise HTTPException(status_code=400, detail=f"Algorithm '{algorithm}' not registered in algorithms table.")

            rows = repo.list_metric_values_by_range(mid, start_dt, end_dt)

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
            repo = AnomalyRepository(conn)
            repo.replace_anomaly_results(mid, algorithm_id, timestamps, results)
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store results: {e}")

    return {"status": "done", "points_processed": len(results)}


@app.get(
    "/anomalies",
    summary="List anomaly results for a metric",
    description="Returns anomaly scores and flags filtered by metric_id and time interval.",
    response_model=list[AnomalyResponseItem],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_anomalies(
    metric_id: str = Query(..., description="Metric ID (numeric)"),
    start: str     = Query(..., description="Start datetime, ISO 8601"),
    end: str       = Query(..., description="End datetime, ISO 8601"),
):
    # Validate start/end as strings so return 400 not 422
    start_dt = _parse_iso_datetime_or_400(start, "start")
    end_dt = _parse_iso_datetime_or_400(end, "end")

    if start_dt >= end_dt:
        raise HTTPException(status_code=400, detail="'start' must be before 'end'")

    # Validate metric_id is numeric
    try:
        mid = int(metric_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid metric_id: '{metric_id}'. Expected a numeric id.")

    try:
        with get_conn() as conn:
            repo = AnomalyRepository(conn)
            rows = repo.list_anomalies_by_metric_and_range(mid, start_dt, end_dt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return [
        {
            "timestamp": r["timestamp"],
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