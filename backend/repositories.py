import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException


def get_conn() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not set")
    return psycopg.connect(database_url, row_factory=dict_row)


class MeasurementRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
    
    def get_readings_with_anomalies(
        self, 
        metric_id: int, 
        start_dt: Optional[datetime] = None, 
        end_dt: Optional[datetime] = None, 
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        conditions = ["r.metric_id = %s"]
        params: list = [metric_id]
        
        if start_dt:
            conditions.append("r.timestamp >= %s")
            params.append(start_dt)
        if end_dt:
            conditions.append("r.timestamp <= %s")
            params.append(end_dt)
        params.append(limit)
        
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT r.id, r.metric_id, r.timestamp, r.value, r.created_at, 
                       EXISTS(SELECT 1 FROM anomaly_results ar 
                              WHERE ar.metric_id = r.metric_id AND ar.timestamp = r.timestamp AND ar.anomaly_flag = true) as is_anomaly
                FROM readings r
                WHERE {' AND '.join(conditions)}
                ORDER BY r.timestamp DESC LIMIT %s
                """,
                params,
            )
            return cur.fetchall()
    
    def get_readings_by_zone(
        self, 
        zone_id: int, 
        start_dt: Optional[datetime] = None, 
        end_dt: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        conditions = ["r.zone_id = %s"]
        params: list = [zone_id]
        
        if start_dt:
            conditions.append("r.timestamp >= %s")
            params.append(start_dt)
        if end_dt:
            conditions.append("r.timestamp <= %s")
            params.append(end_dt)
        
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT r.timestamp, m.name AS metric, r.value
                FROM readings r
                JOIN metrics m ON m.id = r.metric_id
                WHERE {' AND '.join(conditions)}
                ORDER BY r.timestamp ASC
                """,
                params,
            )
            return cur.fetchall()
    
    def get_metric_by_id(self, metric_id: int) -> Optional[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, name, unit FROM metrics WHERE id = %s", (metric_id,))
            return cur.fetchone()


class AnomalyRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
    
    def get_anomalies(
        self, 
        metric_id: int, 
        start_dt: Optional[datetime] = None, 
        end_dt: Optional[datetime] = None, 
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        conditions = ["metric_id = %s"]
        params: list = [metric_id]
        
        if start_dt:
            conditions.append("timestamp >= %s")
            params.append(start_dt)
        if end_dt:
            conditions.append("timestamp <= %s")
            params.append(end_dt)
        params.append(limit)
        
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT metric_id, timestamp, anomaly_score, anomaly_flag, metadata
                FROM anomaly_results
                WHERE {' AND '.join(conditions)}
                ORDER BY timestamp DESC LIMIT %s
                """,
                params,
            )
            return cur.fetchall()
    
    def get_metric_by_id(self, metric_id: int) -> Optional[Dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, name, unit FROM metrics WHERE id = %s", (metric_id,))
            return cur.fetchone()
