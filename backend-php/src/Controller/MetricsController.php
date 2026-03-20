<?php

namespace App\Controller;

use App\Support\ApiResponse;
use App\Support\Database;
use PDOException;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

final class MetricsController
{
    #[Route('/metrics', name: 'metrics_list', methods: ['GET'])]
    public function __invoke(Request $request): JsonResponse
    {
        $entityIdRaw = $request->query->get('entity_id');
        if (!is_numeric($entityIdRaw) || (int) $entityIdRaw <= 0) {
            return ApiResponse::error(400, 'entity_id must be a positive integer.', '/metrics');
        }
        $entityId = (int) $entityIdRaw;

        try {
            $pdo = Database::connectFromEnv();

            $existsStmt = $pdo->prepare('SELECT 1 FROM zones WHERE id = :entity_id');
            $existsStmt->execute(['entity_id' => $entityId]);
            if (!$existsStmt->fetchColumn()) {
                return ApiResponse::error(404, sprintf('Zone %d not found.', $entityId), '/metrics');
            }

            $stmt = $pdo->prepare(
                'SELECT m.id, m.name, m.unit
                 FROM metrics m
                 JOIN devices d ON d.id = m.device_id
                 WHERE d.zone_id = :entity_id
                 ORDER BY m.name'
            );
            $stmt->execute(['entity_id' => $entityId]);
            $rows = $stmt->fetchAll();
        } catch (PDOException) {
            return ApiResponse::error(500, 'Failed to load metrics.', '/metrics');
        }

        $payload = array_map(static fn (array $row): array => [
            'id' => (int) $row['id'],
            'name' => (string) $row['name'],
            'unit' => (string) ($row['unit'] ?? ''),
        ], $rows);

        return new JsonResponse($payload);
    }
}
