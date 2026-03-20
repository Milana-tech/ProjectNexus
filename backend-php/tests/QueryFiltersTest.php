<?php

declare(strict_types=1);

namespace App\Tests;

use App\Tests\Support\Database;
use App\Tests\Support\Fixtures;
use PHPUnit\Framework\TestCase;

final class QueryFiltersTest extends TestCase
{
    private static ?\PDO $pdo = null;

    private static int $entityA;
    private static int $metricA;

    private static int $entityB;
    private static int $metricB;

    public static function setUpBeforeClass(): void
    {
        self::$pdo = Database::pdoFromEnv();
        Database::purge(self::$pdo);

        $fixtures = new Fixtures(self::$pdo);

        $zones = $fixtures->createZones(2);

        $devicesA = $fixtures->createDevices([$zones[0]], 1);
        $metricsA = $fixtures->createMetrics($devicesA, 1);

        $devicesB = $fixtures->createDevices([$zones[1]], 1);
        $metricsB = $fixtures->createMetrics($devicesB, 1);

        self::$entityA = (int) $zones[0];
        self::$metricA = (int) $metricsA[0];

        self::$entityB = (int) $zones[1];
        self::$metricB = (int) $metricsB[0];
    }

    public function testReadingsQueryByEntityIdReturnsOnlyThatEntityAndValuesMatch(): void
    {
        $base = new \DateTimeImmutable('2026-03-20T00:00:00+01:00');

        $a = [
            [
                'timestamp' => $base->modify('+1 second')->format(\DateTimeInterface::ATOM),
                'value' => 1.11,
                'zone_id' => self::$entityA,
                'metric_id' => self::$metricA,
            ],
            [
                'timestamp' => $base->modify('+2 seconds')->format(\DateTimeInterface::ATOM),
                'value' => 2.22,
                'zone_id' => self::$entityA,
                'metric_id' => self::$metricA,
            ],
        ];

        $b = [
            [
                'timestamp' => $base->modify('+3 seconds')->format(\DateTimeInterface::ATOM),
                'value' => 9.99,
                'zone_id' => self::$entityB,
                'metric_id' => self::$metricB,
            ],
        ];

        // Ingest all readings (bulk)
        [$statusIngest, ] = $this->postJson('/ingest', array_merge($a, $b), 10);
        self::assertSame(201, $statusIngest);

        $start = $base->modify('-10 seconds')->format(\DateTimeInterface::ATOM);
        $end = $base->modify('+10 seconds')->format(\DateTimeInterface::ATOM);

        [$status, $rows] = $this->getJson(
            sprintf('/readings?entity_id=%d&start_time=%s&end_time=%s&limit=1000', self::$entityA, rawurlencode($start), rawurlencode($end)),
            5
        );

        self::assertSame(200, $status);
        self::assertIsArray($rows);
        self::assertCount(2, $rows);

        $expectedValuesByEpoch = [];
        foreach ($a as $reading) {
            $expectedValuesByEpoch[(new \DateTimeImmutable($reading['timestamp']))->getTimestamp()] = (float) $reading['value'];
        }

        foreach ($rows as $row) {
            self::assertSame(self::$entityA, (int) ($row['entity_id'] ?? 0));
            self::assertSame(self::$metricA, (int) ($row['metric_id'] ?? 0));

            $ts = (string) ($row['timestamp'] ?? '');
            $epoch = (new \DateTimeImmutable($ts))->getTimestamp();
            self::assertArrayHasKey($epoch, $expectedValuesByEpoch);
            self::assertSame($expectedValuesByEpoch[$epoch], (float) ($row['value'] ?? null));
        }
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

    /** @return array{0:int,1:array<int,mixed>} */
    private function getJson(string $pathWithQuery, int $timeoutSeconds): array
    {
        $url = 'http://localhost:8000' . $pathWithQuery;

        $context = stream_context_create([
            'http' => [
                'method' => 'GET',
                'header' => "Accept: application/json\r\n",
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
