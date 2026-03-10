<?php

namespace App\Controller;

use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

final class DbController
{
    #[Route('/db', name: 'db_check', methods: ['GET'])]
    public function __invoke(): JsonResponse
    {
        $databaseUrl = $_SERVER['DATABASE_URL'] ?? $_ENV['DATABASE_URL'] ?? getenv('DATABASE_URL') ?: null;

        if (!$databaseUrl) {
            return new JsonResponse(['ok' => false, 'error' => 'DATABASE_URL is not set'], 500);
        }

        $parts = parse_url($databaseUrl);
        if ($parts === false) {
            return new JsonResponse(['ok' => false, 'error' => 'DATABASE_URL is invalid'], 500);
        }

        $host = $parts['host'] ?? 'localhost';
        $port = $parts['port'] ?? 5432;
        $user = $parts['user'] ?? '';
        $pass = $parts['pass'] ?? '';
        $dbName = ltrim($parts['path'] ?? '', '/');

        $dsn = sprintf('pgsql:host=%s;port=%d;dbname=%s', $host, $port, $dbName);

        try {
            $pdo = new \PDO($dsn, $user, $pass, [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
            $now = $pdo->query('SELECT now();')->fetchColumn();

            return new JsonResponse(['ok' => true, 'now' => (string) $now]);
        } catch (\Throwable $e) {
            return new JsonResponse(['ok' => false, 'error' => $e->getMessage()], 500);
        }
    }
}
