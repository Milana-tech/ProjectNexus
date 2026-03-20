<?php

namespace App\Controller;

use App\Support\ApiResponse;
use DateTimeImmutable;
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
