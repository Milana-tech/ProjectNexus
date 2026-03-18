<?php

namespace App\Repository;

use DateTimeImmutable;
use PDO;

final class AnomalyRepository
{
    public function __construct(private readonly PDO $pdo)
    {
    }

    public function fetchByMetricAndRange(
        int $metricId,
        DateTimeImmutable $startTime,
        DateTimeImmutable $endTime
    ): array {
        $stmt = $this->pdo->prepare(
            'SELECT timestamp, anomaly_score, anomaly_flag
             FROM anomaly_results
             WHERE metric_id = :metric_id
               AND timestamp BETWEEN :start_time AND :end_time
             ORDER BY timestamp ASC'
        );

        $stmt->bindValue(':metric_id', $metricId, PDO::PARAM_INT);
        $stmt->bindValue(':start_time', $startTime->format(DATE_ATOM));
        $stmt->bindValue(':end_time', $endTime->format(DATE_ATOM));
        $stmt->execute();

        return $stmt->fetchAll();
    }
}
