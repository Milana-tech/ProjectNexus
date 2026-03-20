<?php

namespace App\Controller;

use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

/**
 * Measurements API
 *
 * @OA\Tag(name="Measurements")
 */
final class MeasurementsController
{
    private function getPdo(): ?\PDO
    {
        $databaseUrl = $_SERVER['DATABASE_URL'] ?? $_ENV['DATABASE_URL'] ?? getenv('DATABASE_URL') ?: null;
        if (!$databaseUrl) {
            return null;
        }

        $parts = parse_url($databaseUrl);
        if ($parts === false) {
            return null;
        }

        $host = $parts['host'] ?? 'localhost';
        $port = $parts['port'] ?? 5432;
        $user = $parts['user'] ?? '';
        $pass = $parts['pass'] ?? '';
        $dbName = ltrim($parts['path'] ?? '', '/');

        $dsn = sprintf('pgsql:host=%s;port=%d;dbname=%s', $host, $port, $dbName);

        try {
            return new \PDO($dsn, $user, $pass, [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
        } catch (\Throwable $e) {
            return null;
        }
    }

    /**
     * GET /measurements
     *
     * @OA\Get(
     *     path="/measurements",
     *     summary="List measurements for a metric",
     *     @OA\Parameter(name="metric_id", in="query", required=true, @OA\Schema(type="integer")),
     *     @OA\Parameter(name="start_time", in="query", required=true, @OA\Schema(type="string", format="date-time")),
     *     @OA\Parameter(name="end_time", in="query", required=true, @OA\Schema(type="string", format="date-time")),
     *     @OA\Parameter(name="limit", in="query", required=false, @OA\Schema(type="integer", default=500)),
     *     @OA\Response(response=200, description="OK"),
     *     @OA\Response(response=400, description="Invalid request"),
     *     @OA\Response(response=500, description="Server error")
     * )
     */
    #[Route('/measurements', name: 'measurements_list', methods: ['GET'])]
    public function list(Request $request): JsonResponse
    {
        $pdo = $this->getPdo();
        if ($pdo === null) {
            return new JsonResponse(['error' => 'DB connection failed'], 500);
        }

        $params = $request->query->all();

        // Required params
        if (!isset($params['metric_id']) || !isset($params['start_time']) || !isset($params['end_time'])) {
            return new JsonResponse(['error' => 'metric_id, start_time and end_time are required'], 400);
        }

        $metricId = (int) $params['metric_id'];
        if ($metricId <= 0) {
            return new JsonResponse(['error' => 'metric_id must be a positive integer'], 400);
        }

        try {
            $start = new \DateTimeImmutable($params['start_time']);
            $end = new \DateTimeImmutable($params['end_time']);
        } catch (\Exception $e) {
            return new JsonResponse(['error' => 'start_time/end_time must be valid ISO 8601 datetimes'], 400);
        }

        if ($start >= $end) {
            return new JsonResponse(['error' => 'start_time must be before end_time'], 400);
        }

        $limit = isset($params['limit']) ? (int) $params['limit'] : 500;
        if ($limit <= 0 || $limit > 5000) {
            return new JsonResponse(['error' => 'limit must be between 1 and 5000'], 400);
        }

        try {
            $sql = "SELECT id, metric_id, timestamp, value, zone_id, created_at FROM readings WHERE metric_id = ? AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC LIMIT ?";
            $stmt = $pdo->prepare($sql);
            $stmt->execute([$metricId, $start->format('Y-m-d\TH:i:sP'), $end->format('Y-m-d\TH:i:sP'), $limit]);
            $rows = $stmt->fetchAll(\PDO::FETCH_ASSOC);

            $out = [];
            foreach ($rows as $r) {
                $out[] = [
                    'id' => isset($r['id']) ? (int) $r['id'] : null,
                    'metric_id' => (int) $r['metric_id'],
                    'timestamp' => $r['timestamp'],
                    'value' => isset($r['value']) ? (float) $r['value'] : null,
                    'zone_id' => isset($r['zone_id']) ? (int) $r['zone_id'] : null,
                ];
            }

            return new JsonResponse(['metric_id' => $metricId, 'count' => count($out), 'measurements' => $out]);
        } catch (\Throwable $e) {
            return new JsonResponse(['error' => 'Failed to load measurements'], 500);
        }
    }
}
