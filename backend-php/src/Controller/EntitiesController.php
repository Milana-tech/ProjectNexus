<?php

namespace App\Controller;

use App\Support\ApiResponse;
use App\Support\Database;
use PDOException;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

final class EntitiesController
{
    #[Route('/entities', name: 'entities_list', methods: ['GET'])]
    public function __invoke(): JsonResponse
    {
        try {
            $pdo = Database::connectFromEnv();
            $rows = $pdo->query('SELECT id, name FROM zones ORDER BY name')->fetchAll();
        } catch (PDOException) {
            return ApiResponse::error(500, 'Failed to load entities.', '/entities');
        }

        $payload = array_map(static fn (array $row): array => [
            'id' => (int) $row['id'],
            'name' => (string) $row['name'],
        ], $rows);

        return new JsonResponse($payload);
    }
}
