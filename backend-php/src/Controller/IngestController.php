<?php

namespace App\Controller;

use DateTimeImmutable;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

final class IngestController
{
    #[Route('/ingest', name: 'ingest', methods: ['POST'])]
    public function __invoke(Request $request): JsonResponse
    {
        $payload = $request->getContent();

        if ($payload === '') {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        try {
            $decoded = json_decode($payload, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
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

        if (!preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})$/', $normalized)) {
            return null;
        }

        try {
            return new DateTimeImmutable($normalized);
        } catch (\Throwable) {
            return null;
        }
    }
}
