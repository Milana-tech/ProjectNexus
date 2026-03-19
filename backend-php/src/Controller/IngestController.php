<?php

namespace App\Controller;

use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

final class IngestController
{
    #[Route('/ingest', name: 'ingest', methods: ['POST'])]
    public function __invoke(Request $request): JsonResponse
    {
        $payload = $request->getContent();

        if ($payload === '') {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        try {
            json_decode($payload, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            return new JsonResponse(['error' => 'Invalid JSON'], 400);
        }

        return new JsonResponse(['status' => 'created'], 201);
    }
}
