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
                'description' => 'PHP API for entities, metrics, readings, and anomaly retrieval.',
            ],
            'paths' => [
                '/readings' => [
                    'get' => [
                        'summary' => 'List measurements for one metric in a time range',
                        'parameters' => [
                            ['name' => 'metric_id', 'in' => 'query', 'required' => true, 'schema' => ['type' => 'integer']],
                            ['name' => 'start_time', 'in' => 'query', 'required' => true, 'schema' => ['type' => 'string', 'format' => 'date-time']],
                            ['name' => 'end_time', 'in' => 'query', 'required' => true, 'schema' => ['type' => 'string', 'format' => 'date-time']],
                            ['name' => 'limit', 'in' => 'query', 'required' => false, 'schema' => ['type' => 'integer', 'minimum' => 1, 'maximum' => 10000]],
                        ],
                        'responses' => [
                            '200' => ['description' => 'Successful response'],
                            '400' => ['description' => 'Invalid request'],
                            '404' => ['description' => 'Metric not found'],
                            '500' => ['description' => 'Server error'],
                        ],
                    ],
                ],
                '/anomalies' => [
                    'get' => [
                        'summary' => 'List anomaly results for a metric',
                        'responses' => ['200' => ['description' => 'Successful response']],
                    ],
                ],
            ],
        ];

        return new JsonResponse($spec);
    }
}
