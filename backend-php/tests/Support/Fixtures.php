<?php

declare(strict_types=1);

namespace App\Tests\Support;

final class Fixtures
{
    public function __construct(private readonly \PDO $pdo)
    {
    }

    public function createZones(int $count = 10): array
    {
        $stmt = $this->pdo->prepare('INSERT INTO zones (name, description) VALUES (:name, :description) RETURNING id');

        $ids = [];
        for ($i = 1; $i <= $count; $i++) {
            $stmt->execute([
                'name' => sprintf('Test Zone %d', $i),
                'description' => sprintf('Zone %d', $i),
            ]);
            $ids[] = (int) $stmt->fetchColumn();
        }

        return $ids;
    }

    public function createDevices(array $zoneIds, int $devicesPerZone = 1): array
    {
        $stmt = $this->pdo->prepare('INSERT INTO devices (zone_id, name, type) VALUES (:zone_id, :name, :type) RETURNING id');

        $ids = [];
        foreach ($zoneIds as $zoneId) {
            for ($i = 1; $i <= $devicesPerZone; $i++) {
                $stmt->execute([
                    'zone_id' => (int) $zoneId,
                    'name' => sprintf('Device %d-%d', (int) $zoneId, $i),
                    'type' => 'sensor',
                ]);
                $ids[] = (int) $stmt->fetchColumn();
            }
        }

        return $ids;
    }

    public function createMetrics(array $deviceIds, int $metricsPerDevice = 1): array
    {
        $stmt = $this->pdo->prepare('INSERT INTO metrics (device_id, name, unit) VALUES (:device_id, :name, :unit) RETURNING id');

        $ids = [];
        foreach ($deviceIds as $deviceId) {
            for ($i = 1; $i <= $metricsPerDevice; $i++) {
                $stmt->execute([
                    'device_id' => (int) $deviceId,
                    'name' => sprintf('metric_%d', $i),
                    'unit' => 'unit',
                ]);
                $ids[] = (int) $stmt->fetchColumn();
            }
        }

        return $ids;
    }
}
