<?php

namespace App\Controller;

use App\Support\ApiResponse;
use App\Support\Database;
use DateTimeImmutable;
use PDOException;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

final class IngestController
{
    #[Route('/ingest', name: 'ingest', methods: ['POST'])]
    public function __invoke(Request $request): JsonResponse
    {
        $path = $request->getPathInfo();

        $expectedToken = $_SERVER['INGEST_BEARER_TOKEN'] ?? $_ENV['INGEST_BEARER_TOKEN'] ?? getenv('INGEST_BEARER_TOKEN') ?: null;
        if (!$expectedToken) {
            return ApiResponse::error(500, 'INGEST_BEARER_TOKEN is not set', $path);
        }

        $authHeader = (string) $request->headers->get('Authorization', '');
        if (!str_starts_with($authHeader, 'Bearer ')) {
            return ApiResponse::error(401, 'Unauthorized', $path);
        }
        $providedToken = trim(substr($authHeader, strlen('Bearer ')));
        if ($providedToken === '' || !hash_equals((string) $expectedToken, $providedToken)) {
            return ApiResponse::error(401, 'Unauthorized', $path);
        }

        $payload = $request->getContent();

        if ($payload === '') {
            return ApiResponse::error(400, 'Invalid JSON', $path);
        }

        try {
            $decoded = json_decode($payload, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            return ApiResponse::error(400, 'Invalid JSON', $path);
        }

        if (!is_array($decoded)) {
            return new JsonResponse([
                'errors' => [
                    ['field' => 'body', 'message' => 'Expected a JSON object.'],
                ],
            ], 422);
        }

        $errors = [];

        $entityIdRaw = $decoded['entity_id'] ?? null;
        if ($entityIdRaw === null || $entityIdRaw === '') {
            $errors[] = ['field' => 'entity_id', 'message' => 'entity_id is required.'];
        } elseif (!is_numeric($entityIdRaw) || (int) $entityIdRaw <= 0) {
            $errors[] = ['field' => 'entity_id', 'message' => 'entity_id must be a positive integer.'];
        }

        $metricIdRaw = $decoded['metric_id'] ?? null;
        if ($metricIdRaw === null || $metricIdRaw === '') {
            $errors[] = ['field' => 'metric_id', 'message' => 'metric_id is required.'];
        } elseif (!is_numeric($metricIdRaw) || (int) $metricIdRaw <= 0) {
            $errors[] = ['field' => 'metric_id', 'message' => 'metric_id must be a positive integer.'];
        }

        $value = $decoded['value'] ?? null;
        if ($value === null || $value === '') {
            $errors[] = ['field' => 'value', 'message' => 'value is required.'];
        } elseif (!is_int($value) && !is_float($value) && !(is_string($value) && is_numeric($value))) {
            $errors[] = ['field' => 'value', 'message' => 'value must be numeric.'];
        }

        $timestampRaw = $decoded['timestamp'] ?? null;
        if (!is_string($timestampRaw) || trim($timestampRaw) === '') {
            $errors[] = ['field' => 'timestamp', 'message' => 'timestamp is required.'];
        } elseif ($this->parseIsoDateTime($timestampRaw) === null) {
            $errors[] = ['field' => 'timestamp', 'message' => 'timestamp must be ISO 8601 datetime.'];
        }

        if ($errors !== []) {
            return new JsonResponse(['errors' => $errors], 422);
        }

        $entityId = (int) $entityIdRaw;
        $metricId = (int) $metricIdRaw;
        $numericValue = (float) $value;
        $timestamp = $this->parseIsoDateTime((string) $timestampRaw);

        if ($timestamp === null) {
            return new JsonResponse(['errors' => [['field' => 'timestamp', 'message' => 'timestamp must be ISO 8601 datetime.']]], 422);
        }

        try {
            $pdo = Database::connectFromEnv();

            $zoneExists = $pdo->prepare('SELECT 1 FROM zones WHERE id = :entity_id');
            $zoneExists->execute(['entity_id' => $entityId]);
            if (!$zoneExists->fetchColumn()) {
                return ApiResponse::error(400, sprintf('Unknown entity_id: %d', $entityId), $path);
            }

            $metricExists = $pdo->prepare('SELECT 1 FROM metrics WHERE id = :metric_id');
            $metricExists->execute(['metric_id' => $metricId]);
            if (!$metricExists->fetchColumn()) {
                return ApiResponse::error(400, sprintf('Unknown metric_id: %d', $metricId), $path);
            }

            $statement = $pdo->prepare(
                'INSERT INTO readings (timestamp, value, zone_id, metric_id)
                 VALUES (:timestamp, :value, :zone_id, :metric_id)'
            );
            $statement->execute([
                'timestamp' => $timestamp->format('Y-m-d H:i:sP'),
                'value' => $numericValue,
                'zone_id' => $entityId,
                'metric_id' => $metricId,
            ]);
        } catch (PDOException) {
            return ApiResponse::error(500, 'Failed to persist ingest payload.', $path);
        }

        return new JsonResponse(['status' => 'created'], 201);
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
