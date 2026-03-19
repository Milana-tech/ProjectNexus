<?php

namespace App\Controller;

use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

final class EntityController
{
    private function getPdo(): ?\PDO
    {
        $databaseUrl = $_SERVER['DATABASE_URL'] ?? $_ENV['DATABASE_URL'] ?? getenv('DATABASE_URL') ?: null;
        if (!$databaseUrl) {
            return null;
        }

        $parts = parse_url($databaseUrl);
        if ($parts === false) {
            return null;
        }

        $host = $parts['host'] ?? 'localhost';
        $port = $parts['port'] ?? 5432;
        $user = $parts['user'] ?? '';
        $pass = $parts['pass'] ?? '';
        $dbName = ltrim($parts['path'] ?? '', '/');

        $dsn = sprintf('pgsql:host=%s;port=%d;dbname=%s', $host, $port, $dbName);

        try {
            return new \PDO($dsn, $user, $pass, [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION]);
        } catch (\Throwable $e) {
            return null;
        }
    }

    #[Route('/entities', name: 'entities_list', methods: ['GET'])]
    public function list(Request $request): JsonResponse
    {
        $pdo = $this->getPdo();
        if ($pdo === null) {
            return new JsonResponse(['error' => 'DB connection failed'], 500);
        }

        $params = $request->query->all();
        $where = [];
        $values = [];

        if (isset($params['name'])) {
            $where[] = 'name = ?';
            $values[] = $params['name'];
            unset($params['name']);
        }

        foreach ($params as $k => $v) {
            // metadata ->> key equality
            $where[] = "(metadata ->> ?) = ?";
            $values[] = $k;
            $values[] = $v;
        }

        $sql = 'SELECT id, name, metadata FROM zones';
        if (count($where) > 0) {
            $sql .= ' WHERE ' . implode(' AND ', $where);
        }
        $sql .= ' ORDER BY name';

        try {
            $stmt = $pdo->prepare($sql);
            $stmt->execute($values);
            $rows = $stmt->fetchAll(\PDO::FETCH_ASSOC);
            $out = [];
            foreach ($rows as $r) {
                $out[] = [
                    'id' => (int) $r['id'],
                    'name' => $r['name'],
                    'metadata' => $r['metadata'] !== null ? json_decode($r['metadata'], true) : new \stdClass(),
                ];
            }
            return new JsonResponse($out);
        } catch (\Throwable $e) {
            return new JsonResponse(['error' => 'Failed to load entities'], 500);
        }
    }

    #[Route('/entities/{id}', name: 'entities_patch', methods: ['PATCH'])]
    public function patch(Request $request, int $id): JsonResponse
    {
        $pdo = $this->getPdo();
        if ($pdo === null) {
            return new JsonResponse(['error' => 'DB connection failed'], 500);
        }

        $body = $request->getContent();
        if ($body === '') {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        try {
            $data = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        if (!isset($data['metadata']) || !is_array($data['metadata'])) {
            return new JsonResponse(['error' => "Missing 'metadata' object"], 400);
        }

        $incoming = json_encode($data['metadata']);

        try {
            // ensure entity exists
            $check = $pdo->prepare('SELECT id FROM zones WHERE id = ?');
            $check->execute([$id]);
            if ($check->fetchColumn() === false) {
                return new JsonResponse(['error' => 'Entity not found'], 404);
            }

            $sql = "UPDATE zones SET metadata = COALESCE(metadata, '{}'::jsonb) || ?::jsonb WHERE id = ? RETURNING id, metadata";
            $stmt = $pdo->prepare($sql);
            $stmt->execute([$incoming, $id]);
            $row = $stmt->fetch(\PDO::FETCH_ASSOC);
            return new JsonResponse(['id' => (int) $row['id'], 'metadata' => $row['metadata'] !== null ? json_decode($row['metadata'], true) : new \stdClass()]);
        } catch (\Throwable $e) {
            return new JsonResponse(['error' => 'Failed to update metadata'], 500);
        }
    }
}
