<?php

declare(strict_types=1);

namespace App\Tests;

use App\Tests\Support\Database;
use App\Tests\Support\Fixtures;
use PHPUnit\Framework\TestCase;

final class FixturesTest extends TestCase
{
    private static ?\PDO $pdo = null;

    public static function setUpBeforeClass(): void
    {
        self::$pdo = Database::pdoFromEnv();
        Database::purge(self::$pdo);
    }

    public function testItCanGenerateEntitiesAndMetrics(): void
    {
        $fixtures = new Fixtures(self::$pdo);

        $zoneIds = $fixtures->createZones(10);
        $deviceIds = $fixtures->createDevices($zoneIds, 1);
        $metricIds = $fixtures->createMetrics($deviceIds, 1);

        self::assertCount(10, $zoneIds);
        self::assertCount(10, $deviceIds);
        self::assertCount(10, $metricIds);
    }
}
