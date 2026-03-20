<?php

namespace App\Tests\Controller;

use App\Support\Database;
use PDO;
use Symfony\Bundle\FrameworkBundle\Test\KernelTestCase;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\HttpKernelInterface;

final class IngestControllerTest extends KernelTestCase
{
    public function testValidPayloadReturns201(): void
    {
        $kernel = static::bootKernel();

        $timestamp = '2024-01-01T00:00:00+00:00';
        $this->deleteReading(1, $timestamp);

        $request = Request::create('/ingest', 'POST', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
            'metric_id' => 1,
            'value' => 12.34,
            'timestamp' => $timestamp,
        ], JSON_THROW_ON_ERROR));

        $response = $kernel->handle($request, HttpKernelInterface::MAIN_REQUEST);

        self::assertSame(201, $response->getStatusCode());
        self::assertTrue($this->readingExists(1, $timestamp, 12.34, 1));
    }

    public function testMissingFieldsReturns422(): void
    {
        $kernel = static::bootKernel();

        $request = Request::create('/ingest', 'POST', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
        ], JSON_THROW_ON_ERROR));

        $response = $kernel->handle($request, HttpKernelInterface::MAIN_REQUEST);

        self::assertSame(422, $response->getStatusCode());

        $payload = json_decode((string) $response->getContent(), true);
        self::assertIsArray($payload);
        self::assertArrayHasKey('errors', $payload);
        self::assertIsArray($payload['errors']);
    }

    public function testNoAuthReturns401(): void
    {
        $kernel = static::bootKernel();

        $request = Request::create('/ingest', 'POST', content: json_encode([
            'entity_id' => 1,
            'metric_id' => 1,
            'value' => 12.34,
            'timestamp' => '2024-01-01T00:00:00+00:00',
        ], JSON_THROW_ON_ERROR));

        $response = $kernel->handle($request, HttpKernelInterface::MAIN_REQUEST);

        self::assertSame(401, $response->getStatusCode());
    }

    public function testInvalidTimestampReturns422(): void
    {
        $kernel = static::bootKernel();

        $request = Request::create('/ingest', 'POST', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
            'metric_id' => 1,
            'value' => 12.34,
            'timestamp' => 'not-a-timestamp',
        ], JSON_THROW_ON_ERROR));

        $response = $kernel->handle($request, HttpKernelInterface::MAIN_REQUEST);

        self::assertSame(422, $response->getStatusCode());
    }

    public function testInvalidEntityIdTypeReturns422(): void
    {
        $kernel = static::bootKernel();

        $request = Request::create('/ingest', 'POST', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 'abc',
            'metric_id' => 1,
            'value' => 12.34,
            'timestamp' => '2024-01-01T00:00:00+00:00',
        ], JSON_THROW_ON_ERROR));

        $response = $kernel->handle($request, HttpKernelInterface::MAIN_REQUEST);

        self::assertSame(422, $response->getStatusCode());
    }

    public function testInvalidMetricIdTypeReturns422(): void
    {
        $kernel = static::bootKernel();

        $request = Request::create('/ingest', 'POST', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
            'metric_id' => 'abc',
            'value' => 12.34,
            'timestamp' => '2024-01-01T00:00:00+00:00',
        ], JSON_THROW_ON_ERROR));

        $response = $kernel->handle($request, HttpKernelInterface::MAIN_REQUEST);

        self::assertSame(422, $response->getStatusCode());
    }

    public function testInvalidValueTypeReturns422(): void
    {
        $kernel = static::bootKernel();

        $request = Request::create('/ingest', 'POST', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
            'metric_id' => 1,
            'value' => 'abc',
            'timestamp' => '2024-01-01T00:00:00+00:00',
        ], JSON_THROW_ON_ERROR));

        $response = $kernel->handle($request, HttpKernelInterface::MAIN_REQUEST);

        self::assertSame(422, $response->getStatusCode());
    }

    private function readingExists(int $metricId, string $timestamp, float $value, int $zoneId): bool
    {
        $pdo = Database::connectFromEnv();
        $statement = $pdo->prepare(
            'SELECT 1
              FROM readings
              WHERE metric_id = :metric_id
                AND zone_id = :zone_id
                AND timestamp = :timestamp
                AND ABS(value - :value) < 0.000001'
        );
        $statement->execute([
            'metric_id' => $metricId,
            'zone_id' => $zoneId,
            'timestamp' => $timestamp,
            'value' => $value,
        ]);

        return (bool) $statement->fetchColumn();
    }

    private function deleteReading(int $metricId, string $timestamp): void
    {
        $pdo = Database::connectFromEnv();
        $statement = $pdo->prepare('DELETE FROM readings WHERE metric_id = :metric_id AND timestamp = :timestamp');
        $statement->execute([
            'metric_id' => $metricId,
            'timestamp' => $timestamp,
        ]);
    }
}
