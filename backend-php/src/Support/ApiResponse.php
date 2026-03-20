<?php

namespace App\Support;

use Symfony\Component\HttpFoundation\JsonResponse;

final class ApiResponse
{
    public static function error(int $status, string $message, string $path): JsonResponse
    {
        return new JsonResponse([
            'error' => [
                'status' => $status,
                'message' => $message,
                'path' => $path,
            ],
        ], $status);
    }
}
