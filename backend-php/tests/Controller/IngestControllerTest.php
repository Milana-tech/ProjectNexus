<?php

namespace App\Tests\Controller;

use Symfony\Bundle\FrameworkBundle\Test\WebTestCase;

final class IngestControllerTest extends WebTestCase
{
    public function testValidPayloadReturns201(): void
    {
        $client = static::createClient();

        $client->request('POST', '/ingest', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
            'metric_id' => 1,
            'value' => 12.34,
            'timestamp' => '2024-01-01T00:00:00+00:00',
        ], JSON_THROW_ON_ERROR));

        self::assertResponseStatusCodeSame(201);
    }

    public function testMissingFieldsReturns422(): void
    {
        $client = static::createClient();

        $client->request('POST', '/ingest', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
        ], JSON_THROW_ON_ERROR));

        self::assertResponseStatusCodeSame(422);

        $payload = json_decode((string) $client->getResponse()->getContent(), true);
        self::assertIsArray($payload);
        self::assertArrayHasKey('errors', $payload);
        self::assertIsArray($payload['errors']);
    }

    public function testNoAuthReturns401(): void
    {
        $client = static::createClient();

        $client->request('POST', '/ingest', content: json_encode([
            'entity_id' => 1,
            'metric_id' => 1,
            'value' => 12.34,
            'timestamp' => '2024-01-01T00:00:00+00:00',
        ], JSON_THROW_ON_ERROR));

        self::assertResponseStatusCodeSame(401);
    }

    public function testInvalidTimestampReturns422(): void
    {
        $client = static::createClient();

        $client->request('POST', '/ingest', server: [
            'HTTP_AUTHORIZATION' => 'Bearer test-token',
        ], content: json_encode([
            'entity_id' => 1,
            'metric_id' => 1,
            'value' => 12.34,
            'timestamp' => 'not-a-timestamp',
        ], JSON_THROW_ON_ERROR));

        self::assertResponseStatusCodeSame(422);
    }
}
