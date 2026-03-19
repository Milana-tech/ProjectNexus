<?php

namespace App\Repository;

use DateTimeImmutable;
use PDO;

final class MeasurementRepository
{
    public function __construct(private readonly PDO $pdo)
    {
    }

    public function entityExists(int $entityId): bool
    {
        $stmt = $this->pdo->prepare('SELECT 1 FROM zones WHERE id = :entity_id');
        $stmt->execute(['entity_id' => $entityId]);

        return (bool) $stmt->fetchColumn();
    }

    public function metricExists(int $metricId): bool
    {
        $stmt = $this->pdo->prepare('SELECT 1 FROM metrics WHERE id = :metric_id');
        $stmt->execute(['metric_id' => $metricId]);

        return (bool) $stmt->fetchColumn();
    }

    public function metricBelongsToEntity(int $metricId, int $entityId): bool
    {
        $stmt = $this->pdo->prepare(
            'SELECT 1
             FROM metrics m
             JOIN devices d ON d.id = m.device_id
             WHERE m.id = :metric_id AND d.zone_id = :entity_id'
        );
        $stmt->execute([
            'metric_id' => $metricId,
            'entity_id' => $entityId,
        ]);

        return (bool) $stmt->fetchColumn();
    }

    public function fetchByEntityAndRange(
        int $entityId,
        DateTimeImmutable $startTime,
        DateTimeImmutable $endTime,
        int $limit,
        ?int $metricId = null,
    ): array {
        $sql = 'SELECT r.timestamp, r.value, r.metric_id, r.zone_id AS entity_id
                FROM readings r
                JOIN metrics m ON m.id = r.metric_id
                JOIN devices d ON d.id = m.device_id
                WHERE d.zone_id = :entity_id
                  AND r.zone_id = :entity_id
                  AND r.timestamp BETWEEN :start_time AND :end_time';

        if ($metricId !== null) {
            $sql .= ' AND r.metric_id = :metric_id';
        }

        $sql .= ' ORDER BY r.timestamp ASC LIMIT :row_limit';

        $stmt = $this->pdo->prepare($sql);
        $stmt->bindValue(':entity_id', $entityId, PDO::PARAM_INT);
        $stmt->bindValue(':start_time', $startTime->format(DATE_ATOM));
        $stmt->bindValue(':end_time', $endTime->format(DATE_ATOM));
        $stmt->bindValue(':row_limit', $limit, PDO::PARAM_INT);

        if ($metricId !== null) {
            $stmt->bindValue(':metric_id', $metricId, PDO::PARAM_INT);
        }

        $stmt->execute();

        return $stmt->fetchAll();
    }
}
