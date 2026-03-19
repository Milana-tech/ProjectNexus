<?php

namespace App\Controller;

use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

final class OpenApiController
{
    #[Route('/openapi.json', name: 'openapi_json', methods: ['GET'])]
    public function __invoke(): JsonResponse
    {
        $spec = [
            'openapi' => '3.1.0',
            'info' => [
                'title' => 'Project Nexus PHP API',
                'version' => '1.0.0',
                'description' => 'PHP API for retrieval endpoints.',
            ],
            'paths' => [
                '/readings' => [
                    'get' => [
                        'summary' => 'List measurements for an entity, optionally filtered by metric and time range',
                        'parameters' => [
                            ['name' => 'entity_id', 'in' => 'query', 'required' => true, 'schema' => ['type' => 'integer']],
                            ['name' => 'metric_id', 'in' => 'query', 'required' => false, 'schema' => ['type' => 'integer']],
                            ['name' => 'start_time', 'in' => 'query', 'required' => false, 'schema' => ['type' => 'string', 'format' => 'date-time']],
                            ['name' => 'end_time', 'in' => 'query', 'required' => false, 'schema' => ['type' => 'string', 'format' => 'date-time']],
                            ['name' => 'limit', 'in' => 'query', 'required' => false, 'schema' => ['type' => 'integer', 'minimum' => 1, 'maximum' => 10000]],
                        ],
                        'responses' => [
                            '200' => ['description' => 'Successful response'],
                            '400' => ['description' => 'Invalid request'],
                            '404' => ['description' => 'Entity or metric not found'],
                            '500' => ['description' => 'Server error'],
                        ],
                    ],
                ],
            ],
        ];

        return new JsonResponse($spec);
    }
}
