<?php

namespace App\Controller;

use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

final class ConfigController
{
    #[Route('/config', name: 'app_config', methods: ['GET'])]
    public function __invoke(): JsonResponse
    {
        return new JsonResponse([
            'app_title' => 'Project Nexus - Environmental Dashboard',
            'quick_ranges' => [
                ['label' => 'Last hour', 'ms' => 60 * 60 * 1000],
                ['label' => 'Last 6 h', 'ms' => 6 * 60 * 60 * 1000],
                ['label' => 'Last day', 'ms' => 24 * 60 * 60 * 1000],
                ['label' => 'Last week', 'ms' => 7 * 24 * 60 * 60 * 1000],
            ],
            'default_range_index' => 1,
        ]);
    }
}
