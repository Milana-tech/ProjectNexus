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
        $payload = $request->getContent();

        if ($payload === '') {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        try {
            $data = json_decode($payload, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        if (!is_array($data)) {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        $isBulk = $this->isList($data);
        if ($isBulk) {
            return $this->handleBulk($data);
        }

        return $this->handleSingle($data);
    }

    /** @param array<string,mixed> $data */
    private function handleSingle(array $data): JsonResponse
    {
        $validation = $this->validateReading($data);
        if ($validation !== null) {
            return $validation;
        }

        $timestamp = \DateTimeImmutable::createFromFormat(\DateTimeInterface::ATOM, (string) $data['timestamp']);
        if ($timestamp === false) {
            return new JsonResponse(['error' => 'Validation failed', 'field' => 'timestamp'], 422);
        }

        $zoneId = (int) $data['zone_id'];
        $metricId = (int) $data['metric_id'];
        $value = (float) $data['value'];

        try {
            $pdo = $this->pdoFromEnv();
            $stmt = $pdo->prepare('INSERT INTO readings (timestamp, value, zone_id, metric_id) VALUES (:timestamp, :value, :zone_id, :metric_id)');
            $stmt->execute([
                'timestamp' => $timestamp->format('Y-m-d\TH:i:sP'),
                'value' => $value,
                'zone_id' => $zoneId,
                'metric_id' => $metricId,
            ]);
        } catch (\Throwable $e) {
            return new JsonResponse(['error' => 'Database error'], 500);
        }

        return new JsonResponse(['status' => 'created'], 201);
    }

    /** @param array<int,mixed> $data */
    private function handleBulk(array $data): JsonResponse
    {
        if (count($data) === 0) {
            return new JsonResponse(['error' => 'Validation failed', 'field' => 'payload'], 422);
        }

        foreach ($data as $index => $item) {
            if (!is_array($item)) {
                return new JsonResponse(['error' => 'Validation failed', 'field' => 'payload', 'index' => $index], 422);
            }

            $validation = $this->validateReading($item);
            if ($validation !== null) {
                $body = $validation->getData();
                if (is_array($body)) {
                    $body['index'] = $index;
                    return new JsonResponse($body, $validation->getStatusCode());
                }

                return $validation;
            }
        }

        try {
            $pdo = $this->pdoFromEnv();
            $pdo->beginTransaction();

            $stmt = $pdo->prepare('INSERT INTO readings (timestamp, value, zone_id, metric_id) VALUES (:timestamp, :value, :zone_id, :metric_id)');
            foreach ($data as $item) {
                $timestamp = \DateTimeImmutable::createFromFormat(\DateTimeInterface::ATOM, (string) $item['timestamp']);
                if ($timestamp === false) {
                    throw new \RuntimeException('Invalid timestamp');
                }

                $stmt->execute([
                    'timestamp' => $timestamp->format('Y-m-d\TH:i:sP'),
                    'value' => (float) $item['value'],
                    'zone_id' => (int) $item['zone_id'],
                    'metric_id' => (int) $item['metric_id'],
                ]);
            }

            $pdo->commit();
        } catch (\Throwable $e) {
            if (isset($pdo) && $pdo instanceof \PDO && $pdo->inTransaction()) {
                $pdo->rollBack();
            }

            return new JsonResponse(['error' => 'Database error'], 500);
        }

        return new JsonResponse(['status' => 'created', 'count' => count($data)], 201);
    }

    /** @param array<string,mixed> $data */
    private function validateReading(array $data): ?JsonResponse
    {
        $required = ['timestamp', 'value', 'zone_id', 'metric_id'];
        foreach ($required as $field) {
            if (!array_key_exists($field, $data)) {
                return new JsonResponse(['error' => 'Validation failed', 'field' => $field], 422);
            }
        }

        if (!is_string($data['timestamp'])) {
            return new JsonResponse(['error' => 'Validation failed', 'field' => 'timestamp'], 422);
        }

        $timestamp = \DateTimeImmutable::createFromFormat(\DateTimeInterface::ATOM, $data['timestamp']);
        $errors = \DateTimeImmutable::getLastErrors();
        if ($timestamp === false || ($errors !== false && ($errors['warning_count'] > 0 || $errors['error_count'] > 0))) {
            return new JsonResponse(['error' => 'Validation failed', 'field' => 'timestamp'], 422);
        }

        if (!is_int($data['zone_id']) && !is_float($data['zone_id']) && !is_string($data['zone_id'])) {
            return new JsonResponse(['error' => 'Validation failed', 'field' => 'zone_id'], 422);
        }
        if (!is_int($data['metric_id']) && !is_float($data['metric_id']) && !is_string($data['metric_id'])) {
            return new JsonResponse(['error' => 'Validation failed', 'field' => 'metric_id'], 422);
        }

        if (!is_int($data['value']) && !is_float($data['value'])) {
            return new JsonResponse(['error' => 'Validation failed', 'field' => 'value'], 422);
        }

        return null;
    }

    private function isList(array $data): bool
    {
        $expectedKey = 0;
        foreach ($data as $key => $_value) {
            if ($key !== $expectedKey) {
                return false;
            }
            $expectedKey++;
        }

        return true;
    }

    private function pdoFromEnv(): \PDO
    {
        $databaseUrl = $_SERVER['DATABASE_URL'] ?? $_ENV['DATABASE_URL'] ?? getenv('DATABASE_URL') ?: null;
        if (!$databaseUrl) {
            throw new \RuntimeException('DATABASE_URL is not set');
        }

        $parts = parse_url($databaseUrl);
        if ($parts === false) {
            throw new \RuntimeException('DATABASE_URL is invalid');
        }

        $host = $parts['host'] ?? 'localhost';
        $port = (int) ($parts['port'] ?? 5432);
        $user = $parts['user'] ?? '';
        $pass = $parts['pass'] ?? '';
        $dbName = ltrim($parts['path'] ?? '', '/');

        $dsn = sprintf('pgsql:host=%s;port=%d;dbname=%s', $host, $port, $dbName);

        return new \PDO($dsn, $user, $pass, [
            \PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION,
        ]);
    }
}
