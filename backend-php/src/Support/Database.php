<?php

namespace App\Support;

use PDO;
use PDOException;

final class Database
{
    public static function connectFromEnv(): PDO
    {
        $databaseUrl = $_SERVER['DATABASE_URL'] ?? $_ENV['DATABASE_URL'] ?? getenv('DATABASE_URL') ?: null;
        if (!$databaseUrl) {
            throw new PDOException('DATABASE_URL is not set');
        }

        $parts = parse_url($databaseUrl);
        if ($parts === false) {
            throw new PDOException('DATABASE_URL is invalid');
        }

        $host = $parts['host'] ?? 'localhost';
        $port = (int) ($parts['port'] ?? 5432);
        $user = $parts['user'] ?? '';
        $pass = $parts['pass'] ?? '';
        $dbName = ltrim($parts['path'] ?? '', '/');

        $dsn = sprintf('pgsql:host=%s;port=%d;dbname=%s', $host, $port, $dbName);

        return new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
    }
}
