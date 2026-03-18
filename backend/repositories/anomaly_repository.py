from datetime import datetime
from typing import Any


class AnomalyRepository:
    def __init__(self, conn: Any):
        self.conn = conn

    def metric_exists(self, metric_id: int) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM metrics WHERE id = %s", (metric_id,))
            return cur.fetchone() is not None

    def get_algorithm_id(self, algorithm_name: str) -> int | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM algorithms WHERE name = %s", (algorithm_name,))
            row = cur.fetchone()
            return row["id"] if row else None

    def list_metric_values_by_range(
        self,
        metric_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT timestamp, value
                FROM readings
                WHERE metric_id = %s
                  AND timestamp BETWEEN %s AND %s
                ORDER BY timestamp ASC
                """,
                (metric_id, start_time, end_time),
            )
            return cur.fetchall()

    def replace_anomaly_results(
        self,
        metric_id: int,
        algorithm_id: int,
        timestamps: list[datetime],
        results: list[dict[str, Any]],
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM anomaly_results WHERE metric_id = %s AND algorithm_id = %s",
                (metric_id, algorithm_id),
            )

            for idx, result in enumerate(results):
                cur.execute(
                    """
                    INSERT INTO anomaly_results
                    (metric_id, algorithm_id, timestamp, anomaly_score, anomaly_flag)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        metric_id,
                        algorithm_id,
                        timestamps[idx],
                        result["score"],
                        result["flag"],
                    ),
                )

    def list_anomalies_by_metric_and_range(
        self,
        metric_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT timestamp, anomaly_score, anomaly_flag
                FROM anomaly_results
                WHERE metric_id = %s
                  AND timestamp BETWEEN %s AND %s
                ORDER BY timestamp ASC
                """,
                (metric_id, start_time, end_time),
            )
            return cur.fetchall()
