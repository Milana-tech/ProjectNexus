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

        $entityRaw = $request->query->get('entity_id');
        if (!is_numeric($entityRaw) || (int) $entityRaw <= 0) {
            return ApiResponse::error(400, 'entity_id must be a positive integer.', $path);
        }
        $entityId = (int) $entityRaw;

        $metricId = null;
        $metricRaw = $request->query->get('metric_id');
        if ($metricRaw !== null && $metricRaw !== '') {
            if (!is_numeric($metricRaw) || (int) $metricRaw <= 0) {
                return ApiResponse::error(400, 'metric_id must be a positive integer.', $path);
            }
            $metricId = (int) $metricRaw;
        }

        $startRaw = (string) $request->query->get('start_time', '');
        $endRaw = (string) $request->query->get('end_time', '');

        $now = new DateTimeImmutable('now');
        $start = $startRaw === '' ? $now->modify('-24 hours') : $this->parseIsoDateTime($startRaw);
        if ($start === null) {
            return ApiResponse::error(400, 'Invalid start_time. Use ISO 8601 datetime.', $path);
        }

        $end = $endRaw === '' ? $now : $this->parseIsoDateTime($endRaw);
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

            if (!$repo->entityExists($entityId)) {
                return ApiResponse::error(404, sprintf('entity_id %d not found.', $entityId), $path);
            }

            if ($metricId !== null) {
                if (!$repo->metricExists($metricId)) {
                    return ApiResponse::error(404, sprintf('metric_id %d not found.', $metricId), $path);
                }

                if (!$repo->metricBelongsToEntity($metricId, $entityId)) {
                    return ApiResponse::error(
                        400,
                        'metric_id does not belong to the provided entity_id.',
                        $path,
                    );
                }
            }

            $rows = $repo->fetchByEntityAndRange($entityId, $start, $end, $limit, $metricId);
        } catch (PDOException) {
            return ApiResponse::error(500, 'Database error while retrieving readings.', $path);
        }

        $payload = array_map(static fn (array $row): array => [
            'timestamp' => (new DateTimeImmutable((string) $row['timestamp']))->format(DATE_ATOM),
            'value' => (float) $row['value'],
            'metric_id' => (int) $row['metric_id'],
            'entity_id' => (int) $row['entity_id'],
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
