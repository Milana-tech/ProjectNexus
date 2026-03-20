<?php

namespace App\Repository;

use DateTimeImmutable;
use PDO;

final class MeasurementRepository
{
    public function __construct(private readonly PDO $pdo)
    {
    }

    public function metricExists(int $metricId): bool
    {
        $stmt = $this->pdo->prepare('SELECT 1 FROM metrics WHERE id = :metric_id');
        $stmt->execute(['metric_id' => $metricId]);

        return (bool) $stmt->fetchColumn();
    }

    public function fetchByMetricAndRange(
        int $metricId,
        DateTimeImmutable $startTime,
        DateTimeImmutable $endTime,
        int $limit
    ): array {
        $stmt = $this->pdo->prepare(
            'SELECT metric_id, timestamp, value
             FROM readings
             WHERE metric_id = :metric_id
               AND timestamp BETWEEN :start_time AND :end_time
             ORDER BY timestamp ASC
             LIMIT :row_limit'
        );

        $stmt->bindValue(':metric_id', $metricId, PDO::PARAM_INT);
        $stmt->bindValue(':start_time', $startTime->format(DATE_ATOM));
        $stmt->bindValue(':end_time', $endTime->format(DATE_ATOM));
        $stmt->bindValue(':row_limit', $limit, PDO::PARAM_INT);
        $stmt->execute();

        return $stmt->fetchAll();
    }
}
