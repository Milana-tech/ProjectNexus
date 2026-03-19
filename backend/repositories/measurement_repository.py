from datetime import datetime
from typing import Any


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
