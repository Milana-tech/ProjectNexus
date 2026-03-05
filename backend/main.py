from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import FastAPI, Query, Path, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database import get_connection

# Load environment variables (important if running locally)
load_dotenv()

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
                cur.execute("SELECT id, name FROM zones ORDER BY name;")
                rows = cur.fetchall()

        zones = [{"id": row[0], "name": row[1]} for row in rows]
        return zones

    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/readings/{zone_id}")
def get_readings(
    zone_id: int = Path(..., description="Zone ID to filter readings"),
    start: datetime = Query(None, description="Start datetime filter (ISO format)"),
    end: datetime = Query(None, description="End datetime filter (ISO format)")
):
    """
    Get sensor readings for a specific zone with optional time range filtering.
    
    - **zone_id**: The ID of the zone to get readings for
    - **start**: Optional start datetime (ISO 8601 format). If not provided, defaults to 24 hours ago.
    - **end**: Optional end datetime (ISO 8601 format). If not provided, defaults to now.
    """
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
    if not zone_exists(zone_id):
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    # Fetch readings from database
    readings = fetch_readings(zone_id, start, end)
    
    # Return only the readings array (frontend expects direct array)
    return readings
