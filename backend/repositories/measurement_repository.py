from datetime import datetime
from typing import Any, Optional, List


class MeasurementRepository:
    def __init__(self, conn: Any):
        self.conn = conn

    def metric_exists(self, metric_id: int) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM metrics WHERE id = %s", (metric_id,))
            return cur.fetchone() is not None

    def zone_exists(self, zone_id: int) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM zones WHERE id = %s", (zone_id,))
            return cur.fetchone() is not None

    def list_by_metric_and_range(
        self,
        metric_id: int,
        start_time: datetime,
        end_time: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT metric_id, timestamp, value
                FROM readings
                WHERE metric_id = %s
                  AND timestamp BETWEEN %s AND %s
                ORDER BY timestamp ASC
                LIMIT %s
                """,
                (metric_id, start_time, end_time, limit),
            )
            return cur.fetchall()

    def list_by_zone_and_range(
        self,
        zone_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.timestamp, m.name AS metric, r.value
                FROM readings r
                JOIN metrics m ON m.id = r.metric_id
                WHERE r.zone_id = %s
                  AND r.timestamp BETWEEN %s AND %s
                ORDER BY r.timestamp ASC
                """,
                (zone_id, start_time, end_time),
            )
            return cur.fetchall()

    def get_readings_with_anomalies(
        self, 
        metric_id: int, 
        start_dt: Optional[datetime] = None, 
        end_dt: Optional[datetime] = None, 
        limit: int = 500
    ) -> List[dict[str, Any]]:
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

    def get_metric_by_id(self, metric_id: int) -> Optional[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, name, unit FROM metrics WHERE id = %s", (metric_id,))
            return cur.fetchone()
