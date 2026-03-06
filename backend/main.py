import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database import get_connection

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

    # rows are tuples in the same order as SELECT
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

        # note: this return only names as list of strings!
        zones = [row[0] for row in rows]
        return zones

    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/config")
def get_config():
    """Return UI configuration values so the frontend does not hardcode them.

    Provides:
    - `app_title`: string shown in the dashboard
    - `quick_ranges`: list of {label, ms}
    - `default_range_index`: integer index into `quick_ranges`
    """
    try:
        quick_ranges = [
            {"label": "Last hour", "ms": 60 * 60 * 1000},
            {"label": "Last 6 h", "ms": 6 * 60 * 60 * 1000},
            {"label": "Last day", "ms": 24 * 60 * 60 * 1000},
            {"label": "Last week", "ms": 7 * 24 * 60 * 60 * 1000},
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
    """
    Get sensor readings for a specific zone with optional time range filtering.
    
    - **zone_id**: The ID of the zone to get readings for
    - **start**: Optional start datetime (ISO 8601 format). If not provided, defaults to 24 hours ago.
    - **end**: Optional end datetime (ISO 8601 format). If not provided, defaults to now.
    """
    # Parse zone id (accept numeric strings coming from frontend)
    try:
        zid = int(zone_id)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid zone id: {zone_id}. Expected numeric id.")

    # Set default values if not provided (timezone-aware UTC)
    now = datetime.now(timezone.utc)
    
    if start is None:
        start = now - timedelta(hours=24)
    
    if end is None:
        end = now
    
    # Validation: start must be before end
    if start > end:
        raise HTTPException(
            status_code=400,
            detail=f"Start datetime ({start.isoformat()}) must be before end datetime ({end.isoformat()})"
        )
    
    # Check if zone exists
    if not zone_exists(zid):
        raise HTTPException(status_code=404, detail=f"Zone {zid} not found")
    
    # Fetch readings from database
    readings = fetch_readings(zid, start, end)
    
    # Return only the readings array (frontend expects direct array)
    return readings

@app.post("/anomalies/run")
def run_anomaly(metric_id: str, algorithm: str, start: str, end: str):

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

        timestamps = [r[0] for r in rows]
        values = [r[1] for r in rows]

        results = zscore_detection(values)

        with get_connection() as conn:
            with conn.cursor() as cur:

                for i, r in enumerate(results):

                    cur.execute("""
                        INSERT INTO anomaly_results
                        (metric_id, algorithm_id, timestamp, score, flag)
                        VALUES (%s,%s,%s,%s,%s)
                    """, (
                        metric_id,
                        algorithm,
                        timestamps[i],
                        r["score"],
                        r["flag"]
                    ))

        return {"status": "done", "points_processed": len(results)}

    except Exception as e:
        return {"error": str(e)}

@app.get("/anomalies")
def get_anomalies(metric_id: str, start: str, end: str):

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

        results = []

        for r in rows:
            results.append({
                "timestamp": str(r[0]),
                "score": r[1],
                "flag": r[2]
            })

        return results

    except Exception as e:
        return {"error": str(e)}