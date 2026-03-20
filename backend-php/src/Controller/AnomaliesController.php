<?php

namespace App\Controller;

use App\Repository\AnomalyRepository;
use App\Support\ApiResponse;
use App\Support\Database;
use DateTimeImmutable;
use PDOException;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

final class AnomaliesController
{
    #[Route('/anomalies', name: 'anomalies_list', methods: ['GET'])]
    public function __invoke(Request $request): JsonResponse
    {
        $path = $request->getPathInfo();

        $metricIdRaw = $request->query->get('metric_id');
        if (!is_numeric($metricIdRaw) || (int) $metricIdRaw <= 0) {
            return ApiResponse::error(400, 'metric_id must be a positive integer.', $path);
        }
        $metricId = (int) $metricIdRaw;

        $startRaw = (string) $request->query->get('start', '');
        $endRaw = (string) $request->query->get('end', '');

        $start = $this->parseIsoDateTime($startRaw);
        if ($start === null) {
            return ApiResponse::error(400, 'Invalid start. Use ISO 8601 datetime.', $path);
        }

        $end = $this->parseIsoDateTime($endRaw);
        if ($end === null) {
            return ApiResponse::error(400, 'Invalid end. Use ISO 8601 datetime.', $path);
        }

        if ($end <= $start) {
            return ApiResponse::error(400, 'start must be before end.', $path);
        }

        try {
            $pdo = Database::connectFromEnv();
            $repo = new AnomalyRepository($pdo);
            $rows = $repo->fetchByMetricAndRange($metricId, $start, $end);
        } catch (PDOException) {
            return ApiResponse::error(500, 'Database error while retrieving anomalies.', $path);
        }

        $payload = array_map(static fn (array $row): array => [
            'timestamp' => (new DateTimeImmutable((string) $row['timestamp']))->format(DATE_ATOM),
            'score' => $row['anomaly_score'] === null ? null : (float) $row['anomaly_score'],
            'flag' => (bool) $row['anomaly_flag'],
        ], $rows);

        return new JsonResponse($payload);
    }

    private function parseIsoDateTime(string $value): ?DateTimeImmutable
    {
        $normalized = trim($value);
        if ($normalized === '') {
            return null;
        }

        if (str_ends_with($normalized, 'Z')) {
            $normalized = substr($normalized, 0, -1).'+00:00';
        }

        try {
            return new DateTimeImmutable($normalized);
        } catch (\Throwable) {
            return null;
        }
    }
}
