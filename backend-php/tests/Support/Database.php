<?php

declare(strict_types=1);

namespace App\Tests\Support;

final class Database
{
    public static function pdoFromEnv(): \PDO
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

    public static function purge(
        \PDO $pdo,
        array $tables = ['readings', 'metrics', 'devices', 'zones', 'forecast_results', 'anomaly_results', 'algorithms']
    ): void {
        $pdo->exec('BEGIN');
        try {
            $sql = sprintf('TRUNCATE %s RESTART IDENTITY CASCADE', implode(', ', $tables));
            $pdo->exec($sql);
            $pdo->exec('COMMIT');
        } catch (\Throwable $e) {
            $pdo->exec('ROLLBACK');
            throw $e;
        }
    }
}
