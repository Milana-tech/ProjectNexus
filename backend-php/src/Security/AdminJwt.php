<?php

namespace App\Security;

use Firebase\JWT\JWT;
use Firebase\JWT\Key;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException;

final class AdminJwt
{
    public static function assertAdmin(Request $request): void
    {
        $auth = $request->headers->get('Authorization');
        if (!$auth || !str_starts_with($auth, 'Bearer ')) {
            throw new AccessDeniedHttpException('Admin token required');
        }

        $token = trim(substr($auth, 7));
        if ($token === '') {
            throw new AccessDeniedHttpException('Admin token required');
        }

        $secret = $_SERVER['ADMIN_JWT_SECRET'] ?? $_ENV['ADMIN_JWT_SECRET'] ?? getenv('ADMIN_JWT_SECRET') ?: null;
        if (!$secret) {
            throw new AccessDeniedHttpException('Admin token required');
        }

        try {
            $decoded = (array) JWT::decode($token, new Key($secret, 'HS256'));
        } catch (\Throwable $e) {
            throw new AccessDeniedHttpException('Admin token required');
        }

        if (self::hasAdminClaim($decoded)) {
            return;
        }

        throw new AccessDeniedHttpException('Admin token required');
    }

    /** @param array<string, mixed> $decoded */
    private static function hasAdminClaim(array $decoded): bool
    {
        if (isset($decoded['admin']) && $decoded['admin'] === true) {
            return true;
        }

        if (isset($decoded['roles']) && is_array($decoded['roles'])) {
            foreach ($decoded['roles'] as $role) {
                if (is_string($role) && strtolower($role) === 'admin') {
                    return true;
                }
            }
        }

        if (isset($decoded['scope']) && is_string($decoded['scope'])) {
            $scopes = preg_split('/\s+/', trim($decoded['scope'])) ?: [];
            foreach ($scopes as $scope) {
                if (strtolower($scope) === 'admin') {
                    return true;
                }
            }
        }

        if (isset($decoded['scopes']) && is_array($decoded['scopes'])) {
            foreach ($decoded['scopes'] as $scope) {
                if (is_string($scope) && strtolower($scope) === 'admin') {
                    return true;
                }
            }
        }

        return false;
    }
}
