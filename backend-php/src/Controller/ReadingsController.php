<?php

namespace App\Controller;

use App\Repository\MeasurementRepository;
use App\Support\ApiResponse;
use App\Support\Database;
use DateTimeImmutable;
use PDOException;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

final class ReadingsController
{
    #[Route('/readings', name: 'readings_list', methods: ['GET'])]
    public function __invoke(Request $request): JsonResponse
    {
        $path = $request->getPathInfo();

        $metricIdRaw = $request->query->get('metric_id');
        $entityIdRaw = $request->query->get('entity_id');

        $metricId = null;
        if ($metricIdRaw !== null) {
            if (!is_numeric($metricIdRaw) || (int) $metricIdRaw <= 0) {
                return ApiResponse::error(400, 'metric_id must be a positive integer.', $path);
            }
            $metricId = (int) $metricIdRaw;
        }

        $entityId = null;
        if ($entityIdRaw !== null) {
            if (!is_numeric($entityIdRaw) || (int) $entityIdRaw <= 0) {
                return ApiResponse::error(400, 'entity_id must be a positive integer.', $path);
            }
            $entityId = (int) $entityIdRaw;
        }

        if ($metricId === null && $entityId === null) {
            return ApiResponse::error(400, 'Either metric_id or entity_id query parameter is required.', $path);
        }

        $startRaw = (string) ($request->query->get('start_time') ?? $request->query->get('start') ?? '');
        $endRaw = (string) ($request->query->get('end_time') ?? $request->query->get('end') ?? '');

        if ($startRaw === '' || $endRaw === '') {
            return ApiResponse::error(400, 'Both start_time and end_time query parameters are required.', $path);
        }

        $start = $this->parseIsoDateTime($startRaw);
        if ($start === null) {
            return ApiResponse::error(400, 'Invalid start_time. Use ISO 8601 datetime.', $path);
        }

        $end = $this->parseIsoDateTime($endRaw);
        if ($end === null) {
            return ApiResponse::error(400, 'Invalid end_time. Use ISO 8601 datetime.', $path);
        }

        if ($end < $start) {
            return ApiResponse::error(400, 'end_time must be after or equal to start_time.', $path);
        }

        $limitRaw = $request->query->get('limit', '2000');
        if (!is_numeric($limitRaw)) {
            return ApiResponse::error(400, 'limit must be numeric.', $path);
        }
        $limit = (int) $limitRaw;
        if ($limit < 1 || $limit > 10000) {
            return ApiResponse::error(400, 'limit must be between 1 and 10000.', $path);
        }

        try {
            $pdo = Database::connectFromEnv();
            $repo = new MeasurementRepository($pdo);

            if ($metricId !== null) {
                if (!$repo->metricExists($metricId)) {
                    return ApiResponse::error(404, sprintf('metric_id %d not found.', $metricId), $path);
                }

                $rows = $repo->fetchByMetricAndRange($metricId, $start, $end, $limit);
            } else {
                if ($entityId === null) {
                    return ApiResponse::error(400, 'Either metric_id or entity_id query parameter is required.', $path);
                }

                if (!$repo->entityExists($entityId)) {
                    return ApiResponse::error(404, sprintf('entity_id %d not found.', $entityId), $path);
                }

                $rows = $repo->fetchByEntityAndRange($entityId, $start, $end, $limit);
            }
        } catch (PDOException $e) {
            return ApiResponse::error(500, 'Database error while retrieving readings.', $path);
        }

        $payload = array_map(static fn (array $row): array => [
            'timestamp' => (new DateTimeImmutable((string) $row['timestamp']))->format(DATE_ATOM),
            'value' => (float) $row['value'],
            'metric_id' => (int) $row['metric_id'],
            'entity_id' => (int) ($row['zone_id'] ?? 0),
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
