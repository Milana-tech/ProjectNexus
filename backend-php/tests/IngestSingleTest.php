<?php

declare(strict_types=1);

namespace App\Tests;

use App\Tests\Support\Database;
use App\Tests\Support\Fixtures;
use PHPUnit\Framework\TestCase;

final class IngestSingleTest extends TestCase
{
    private static ?\PDO $pdo = null;
    private static array $zoneIds = [];
    private static array $metricIds = [];

    public static function setUpBeforeClass(): void
    {
        self::$pdo = Database::pdoFromEnv();
        Database::purge(self::$pdo);

        $fixtures = new Fixtures(self::$pdo);
        $zones = $fixtures->createZones(1);
        $devices = $fixtures->createDevices($zones, 1);
        $metrics = $fixtures->createMetrics($devices, 1);

        self::$zoneIds = $zones;
        self::$metricIds = $metrics;
    }

    public function testValidSingleReadingReturns201AndPersistsRecord(): void
    {
        $payload = [
            'timestamp' => '2026-03-19T21:00:00+01:00',
            'value' => 12.34,
            'zone_id' => self::$zoneIds[0],
            'metric_id' => self::$metricIds[0],
        ];

        [$status, $body] = $this->postJson('/ingest', $payload);

        self::assertSame(201, $status);
        self::assertSame('created', $body['status'] ?? null);

        $stmt = self::$pdo->prepare('SELECT timestamp, value, zone_id, metric_id FROM readings ORDER BY id DESC LIMIT 1');
        $stmt->execute();
        $row = $stmt->fetch(\PDO::FETCH_ASSOC);

        self::assertIsArray($row);
        self::assertSame($payload['zone_id'], (int) $row['zone_id']);
        self::assertSame($payload['metric_id'], (int) $row['metric_id']);
        $expectedTs = new \DateTimeImmutable($payload['timestamp']);
        $actualTs = new \DateTimeImmutable((string) $row['timestamp']);
        self::assertSame($expectedTs->getTimestamp(), $actualTs->getTimestamp());
        self::assertSame($payload['value'], (float) $row['value']);
    }

    public function testMissingValueReturns422AndFieldName(): void
    {
        $payload = [
            'timestamp' => '2026-03-19T21:00:00+01:00',
            'zone_id' => self::$zoneIds[0],
            'metric_id' => self::$metricIds[0],
        ];

        [$status, $body] = $this->postJson('/ingest', $payload);

        self::assertSame(422, $status);
        self::assertSame('value', $body['field'] ?? null);
    }

    public function testStringValueReturns422(): void
    {
        $payload = [
            'timestamp' => '2026-03-19T21:00:00+01:00',
            'value' => 'not-a-number',
            'zone_id' => self::$zoneIds[0],
            'metric_id' => self::$metricIds[0],
        ];

        [$status, $body] = $this->postJson('/ingest', $payload);

        self::assertSame(422, $status);
        self::assertSame('value', $body['field'] ?? null);
    }

    public function testInvalidTimestampReturns422(): void
    {
        $payload = [
            'timestamp' => 'yesterday',
            'value' => 1.0,
            'zone_id' => self::$zoneIds[0],
            'metric_id' => self::$metricIds[0],
        ];

        [$status, $body] = $this->postJson('/ingest', $payload);

        self::assertSame(422, $status);
        self::assertSame('timestamp', $body['field'] ?? null);
    }

    public function testMalformedJsonReturns400(): void
    {
        [$status, $body] = $this->postRaw('/ingest', '{"timestamp":');

        self::assertSame(400, $status);
        self::assertSame('Invalid JSON', $body['error'] ?? null);
    }

    /** @return array{0:int,1:array<string,mixed>} */
    private function postJson(string $path, array $payload): array
    {
        return $this->postRaw($path, json_encode($payload, JSON_THROW_ON_ERROR));
    }

    /** @return array{0:int,1:array<string,mixed>} */
    private function postRaw(string $path, string $raw): array
    {
        $url = 'http://localhost:8000' . $path;

        $context = stream_context_create([
            'http' => [
                'method' => 'POST',
                'header' => "Content-Type: application/json\r\n",
                'content' => $raw,
                'ignore_errors' => true,
                'timeout' => 5,
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
