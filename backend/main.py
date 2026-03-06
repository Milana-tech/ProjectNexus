import psycopg
from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from typing import Any
from database import get_connection
from anomaly import get_algorithm

app = FastAPI(title="Project Nexus API")

def zone_exists(zone_id: int) -> bool:
    """Check if a zone exists in the database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM zones WHERE id = %s;", (zone_id,))
            return cur.fetchone() is not None

def fetch_readings(zone_id: int, start_dt: datetime, end_dt: datetime) -> list[dict[str, Any]]:
    """Fetch sensor readings for a specific zone within a time range."""
    sql = """
        SELECT timestamp, temperature, humidity
        FROM sensor_readings
        WHERE zone_id = %s
          AND timestamp BETWEEN %s AND %s
        ORDER BY timestamp ASC;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (zone_id, start_dt, end_dt))
            rows = cur.fetchall()

    return [
        {
            "timestamp": row[0].isoformat(),
            "temperature": row[1],
            "humidity": row[2],
        }
        for row in rows
    ]

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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db")
def db_check():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT now();")
                (now,) = cur.fetchone()
        return {"ok": True, "now": str(now)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/zones")
def get_zones():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT name
                    FROM zones
                    ORDER BY name;
                """)
                rows = cur.fetchall()
        zones = [row[0] for row in rows]
        return zones
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/config")
def get_config():
    try:
        quick_ranges = [
            {"label": "Last hour",  "ms": 60 * 60 * 1000},
            {"label": "Last 6 h",   "ms": 6 * 60 * 60 * 1000},
            {"label": "Last day",   "ms": 24 * 60 * 60 * 1000},
            {"label": "Last week",  "ms": 7 * 24 * 60 * 60 * 1000},
        ]
        return {
            "app_title": "Project Nexus — Environmental Dashboard",
            "quick_ranges": quick_ranges,
            "default_range_index": 1,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/readings/{zone_id}")
def get_readings(
    zone_id: str = Path(..., description="Zone ID to filter readings (numeric id expected)"),
    start: datetime = Query(None, description="Start datetime filter (ISO format)"),
    end: datetime = Query(None, description="End datetime filter (ISO format)")
):
    try:
        zid = int(zone_id)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid zone id: {zone_id}. Expected numeric id.")

    now = datetime.now(timezone.utc)

    if start is None:
        start = now - timedelta(hours=24)
    if end is None:
        end = now

    if start > end:
        raise HTTPException(
            status_code=400,
            detail=f"Start datetime ({start.isoformat()}) must be before end datetime ({end.isoformat()})"
        )

    if not zone_exists(zid):
        raise HTTPException(status_code=404, detail=f"Zone {zid} not found")

    readings = fetch_readings(zid, start, end)
    return readings

@app.post("/anomalies/run")
def run_anomaly(
    metric_id: str  = Query(..., description="Metric ID to run detection on"),
    algorithm: str  = Query(..., description="Algorithm name, e.g. 'zscore'"),
    start: datetime = Query(..., description="Start datetime, ISO 8601"),
    end: datetime   = Query(..., description="End datetime, ISO 8601"),
):
    # Validate algorithm exists
    try:
        fn = get_algorithm(algorithm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate time range
    if start >= end:
        raise HTTPException(status_code=400, detail="'start' must be before 'end'")

    # Fetch data
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT timestamp, value
                    FROM metrics
                    WHERE metric_id = %s
                    AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp
                """, (metric_id, start, end))
                rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Validate metric has data
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for metric_id '{metric_id}' in the given time range"
        )

    timestamps = [r[0] for r in rows]
    values     = [r[1] for r in rows]

    # Run the algorithm
    results = fn(values)

    # Store results (clear old ones first to avoid duplicates)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM anomaly_results WHERE metric_id = %s",
                    (metric_id,)
                )
                for i, r in enumerate(results):
                    cur.execute("""
                        INSERT INTO anomaly_results
                        (metric_id, algorithm_id, timestamp, score, flag)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (metric_id, algorithm, timestamps[i], r["score"], r["flag"]))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store results: {e}")

    return {"status": "done", "points_processed": len(results)}

@app.get("/anomalies")
def get_anomalies(
    metric_id: str      = Query(..., description="Metric ID to retrieve results for"),
    start: datetime     = Query(..., description="Start datetime, ISO 8601"),
    end: datetime       = Query(..., description="End datetime, ISO 8601"),
):
    if start >= end:
        raise HTTPException(status_code=400, detail="'start' must be before 'end'")

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT timestamp, score, flag
                    FROM anomaly_results
                    WHERE metric_id = %s
                    AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp
                """, (metric_id, start, end))
                rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return [
        {"timestamp": str(r[0]), "score": r[1], "flag": r[2]}
        for r in rows
    ]