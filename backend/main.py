from anomaly import zscore_detection
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import get_connection
from anomaly import zscore_detection

# Load environment variables (important if running locally)
load_dotenv()

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