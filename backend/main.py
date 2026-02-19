import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import get_connection

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
                cur.execute("SELECT id, name FROM zones ORDER BY name;")
                rows = cur.fetchall()

        zones = [{"id": row[0], "name": row[1]} for row in rows]
        return zones

    except Exception as e:
        return {"ok": False, "error": str(e)}
