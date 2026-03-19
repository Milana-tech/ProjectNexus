<?php

namespace App\Controller;

use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

final class IngestController
{
    #[Route('/ingest', name: 'ingest', methods: ['POST'])]
    public function __invoke(Request $request): JsonResponse
    {
        $body = $request->getContent();
        if ($body === '') {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        try {
            $payload = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        // Normalize to array of items
        $items = is_array($payload) && array_values($payload) === $payload ? $payload : [$payload];
        if (count($items) === 0) {
            return new JsonResponse(['error' => 'Empty payload'], 400);
        }

        // Validate items and collect ids
        $validated = [];
        $zoneIds = [];
        $metricIds = [];

        foreach ($items as $i => $it) {
            if (!is_array($it)) {
                return new JsonResponse(['error' => "Item {$i} is not an object"], 400);
            }
            $zone = $it['entity_id'] ?? $it['zone_id'] ?? null;
            $metric = $it['metric_id'] ?? null;
            $value = $it['value'] ?? null;
            $ts = $it['timestamp'] ?? null;

            if ($zone === null || $metric === null || $value === null || $ts === null) {
                return new JsonResponse(['error' => "Item {$i} missing required fields (entity_id|metric_id|value|timestamp)"], 400);
            }

            if (!is_numeric($value)) {
                return new JsonResponse(['error' => "Item {$i} value must be numeric"], 400);
            }

            try {
                $dt = new \DateTimeImmutable($ts);
            } catch (\Exception $e) {
                return new JsonResponse(['error' => "Item {$i} timestamp invalid: {$ts}"], 400);
            }

            $zoneIds[] = (int) $zone;
            $metricIds[] = (int) $metric;

            $validated[] = [
                'zone_id' => (int) $zone,
                'metric_id' => (int) $metric,
                'value' => (float) $value,
                'timestamp' => $dt->format('Y-m-d H:i:sP'),
            ];
        }

        // DB connection via DATABASE_URL
        $databaseUrl = $_SERVER['DATABASE_URL'] ?? $_ENV['DATABASE_URL'] ?? getenv('DATABASE_URL') ?: null;
        if (!$databaseUrl) {
            return new JsonResponse(['error' => 'DATABASE_URL not configured'], 500);
        }

        $parts = parse_url($databaseUrl);
        if ($parts === false) {
            return new JsonResponse(['error' => 'DATABASE_URL invalid'], 500);
        }

        $host = $parts['host'] ?? 'localhost';
        $port = $parts['port'] ?? 5432;
        $user = $parts['user'] ?? '';
        $pass = $parts['pass'] ?? '';
        $dbName = ltrim($parts['path'] ?? '', '/');

        $dsn = sprintf('pgsql:host=%s;port=%d;dbname=%s', $host, $port, $dbName);

        try {
            $pdo = new \PDO($dsn, $user, $pass, [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
        } catch (\Throwable $e) {
            return new JsonResponse(['error' => 'DB connection failed'], 500);
        }

        // Pre-flight: ensure zones and metrics exist
        $zoneIds = array_values(array_unique($zoneIds));
        $metricIds = array_values(array_unique($metricIds));

        $placeholdersZone = implode(',', array_fill(0, count($zoneIds), '?')) ?: 'NULL';
        $placeholdersMetric = implode(',', array_fill(0, count($metricIds), '?')) ?: 'NULL';

        $existingZones = [];
        $existingMetrics = [];

        // Optimized pre-flight: fetch existing ids with a single query when possible
        try {
            if (count($zoneIds) > 0 && count($metricIds) > 0) {
                // Build placeholders for both sets
                $placeholdersBoth = implode(',', array_fill(0, count($zoneIds) + count($metricIds), '?'));
                // We'll select id and type so we can separate results
                $sql = "SELECT id, 'zone' AS kind FROM zones WHERE id IN (" . implode(',', array_fill(0, count($zoneIds), '?')) . ")"
                     . " UNION ALL "
                     . "SELECT id, 'metric' AS kind FROM metrics WHERE id IN (" . implode(',', array_fill(0, count($metricIds), '?')) . ")";

                $stmt = $pdo->prepare($sql);
                $stmt->execute(array_merge($zoneIds, $metricIds));
                $rows = $stmt->fetchAll(\PDO::FETCH_ASSOC);
                foreach ($rows as $r) {
                    if (($r['kind'] ?? '') === 'zone') {
                        $existingZones[] = $r['id'];
                    } else {
                        $existingMetrics[] = $r['id'];
                    }
                }
            } elseif (count($zoneIds) > 0) {
                $stmt = $pdo->prepare("SELECT id FROM zones WHERE id IN (" . implode(',', array_fill(0, count($zoneIds), '?')) . ")");
                $stmt->execute($zoneIds);
                $existingZones = $stmt->fetchAll(\PDO::FETCH_COLUMN, 0);
            } elseif (count($metricIds) > 0) {
                $stmt = $pdo->prepare("SELECT id FROM metrics WHERE id IN (" . implode(',', array_fill(0, count($metricIds), '?')) . ")");
                $stmt->execute($metricIds);
                $existingMetrics = $stmt->fetchAll(\PDO::FETCH_COLUMN, 0);
            }
        } catch (\Throwable $e) {
            return new JsonResponse(['error' => 'DB validation query failed'], 500);
        }

        $missingZones = array_values(array_diff($zoneIds, array_map('intval', $existingZones)));
        $missingMetrics = array_values(array_diff($metricIds, array_map('intval', $existingMetrics)));

        if (count($missingZones) > 0 || count($missingMetrics) > 0) {
            $msg = [];
            if (count($missingZones) > 0) {
                $msg[] = 'entity_id(s) not found: ' . implode(', ', $missingZones);
            }
            if (count($missingMetrics) > 0) {
                $msg[] = 'metric_id(s) not found: ' . implode(', ', $missingMetrics);
            }
            return new JsonResponse(['error' => 'Pre-flight check failed', 'message' => implode('; ', $msg), 'missing_entity_ids' => $missingZones, 'missing_metric_ids' => $missingMetrics], 400);
        }

        // Build single multi-row INSERT into readings (metric_id, timestamp, value, zone_id)
        $valuesSql = [];
        $params = [];
        foreach ($validated as $v) {
            $valuesSql[] = '(?, ?, ?, ?)';
            $params[] = $v['metric_id'];
            $params[] = $v['timestamp'];
            $params[] = $v['value'];
            $params[] = $v['zone_id'];
        }

        $sql = 'INSERT INTO readings (metric_id, timestamp, value, zone_id) VALUES ' . implode(', ', $valuesSql);

        try {
            $pdo->beginTransaction();
            $stmt = $pdo->prepare($sql);
            $stmt->execute($params);
            $pdo->commit();
            return new JsonResponse(['inserted' => count($validated)], 201);
        } catch (\Throwable $e) {
            try { $pdo->rollBack(); } catch (\Throwable $ignore) {}
            return new JsonResponse(['error' => 'DB insert failed'], 500);
        }
    }
}
