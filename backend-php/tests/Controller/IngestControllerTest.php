<?php

namespace App\Tests\Controller;

use Symfony\Bundle\FrameworkBundle\Test\KernelTestCase;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\HttpKernelInterface;

final class IngestControllerTest extends KernelTestCase
{
    public function testValidPayloadReturns201(): void
    {
        $kernel = static::bootKernel();

        $request = Request::create('/ingest', 'POST', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
            'metric_id' => 1,
            'value' => 12.34,
            'timestamp' => '2024-01-01T00:00:00+00:00',
        ], JSON_THROW_ON_ERROR));

        $response = $kernel->handle($request, HttpKernelInterface::MAIN_REQUEST);

        self::assertSame(201, $response->getStatusCode());
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
}
