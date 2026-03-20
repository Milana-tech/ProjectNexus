<?php

declare(strict_types=1);

namespace App\Tests;

use App\Tests\Support\Database;
use App\Tests\Support\Fixtures;
use PHPUnit\Framework\TestCase;

final class IngestBulkTest extends TestCase
{
    private static ?\PDO $pdo = null;
    private static int $zoneId;
    private static int $metricId;

    public static function setUpBeforeClass(): void
    {
        self::$pdo = Database::pdoFromEnv();
        Database::purge(self::$pdo);

        $fixtures = new Fixtures(self::$pdo);
        $zones = $fixtures->createZones(1);
        $devices = $fixtures->createDevices($zones, 1);
        $metrics = $fixtures->createMetrics($devices, 1);

        self::$zoneId = (int) $zones[0];
        self::$metricId = (int) $metrics[0];
    }

    public function testBulkIngest500ItemsReturns201AndInsertsExactly500(): void
    {
        $before = $this->countReadings();

        $payload = [];
        $base = new \DateTimeImmutable('2026-03-20T00:00:00+01:00');
        for ($i = 0; $i < 500; $i++) {
            $payload[] = [
                'timestamp' => $base->modify(sprintf('+%d seconds', $i))->format(\DateTimeInterface::ATOM),
                'value' => 10.0 + ($i / 1000),
                'zone_id' => self::$zoneId,
                'metric_id' => self::$metricId,
            ];
        }

        $start = microtime(true);
        [$status, $body] = $this->postJson('/ingest', $payload, 10);
        $elapsed = microtime(true) - $start;

        self::assertSame(201, $status);
        self::assertSame('created', $body['status'] ?? null);
        self::assertSame(500, (int) ($body['count'] ?? 0));
        self::assertLessThan(10.0, $elapsed);

        $after = $this->countReadings();
        self::assertSame($before + 500, $after);
    }

    private function countReadings(): int
    {
        $stmt = self::$pdo->query('SELECT COUNT(*) FROM readings');
        return (int) $stmt->fetchColumn();
    }

    /** @return array{0:int,1:array<string,mixed>} */
    private function postJson(string $path, array $payload, int $timeoutSeconds): array
    {
        $url = 'http://localhost:8000' . $path;

        $context = stream_context_create([
            'http' => [
                'method' => 'POST',
                'header' => "Content-Type: application/json\r\n",
                'content' => json_encode($payload, JSON_THROW_ON_ERROR),
                'ignore_errors' => true,
                'timeout' => $timeoutSeconds,
            ],
        ]);

        $response = file_get_contents($url, false, $context);
        $headers = $http_response_header ?? [];

        $status = 0;
        if ($headers !== []) {
            $parts = explode(' ', $headers[0]);
            if (isset($parts[1])) {
                $status = (int) $parts[1];
            }
        }

        $decoded = [];
        if (is_string($response) && $response !== '') {
            $decoded = json_decode($response, true) ?? [];
        }

        return [$status, is_array($decoded) ? $decoded : []];
    }
}
