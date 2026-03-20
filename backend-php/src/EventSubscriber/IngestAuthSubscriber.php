<?php

namespace App\EventSubscriber;

use App\Support\ApiResponse;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;
use Symfony\Component\HttpKernel\Event\RequestEvent;
use Symfony\Component\HttpKernel\KernelEvents;

final class IngestAuthSubscriber implements EventSubscriberInterface
{
    public static function getSubscribedEvents(): array
    {
        return [
            KernelEvents::REQUEST => ['onKernelRequest', 100],
        ];
    }

    public function onKernelRequest(RequestEvent $event): void
    {
        if (!$event->isMainRequest()) {
            return;
        }

        $request = $event->getRequest();
        if ($request->getPathInfo() !== '/ingest' || $request->getMethod() !== 'POST') {
            return;
        }

        $expectedToken = $_SERVER['INGEST_BEARER_TOKEN'] ?? $_ENV['INGEST_BEARER_TOKEN'] ?? getenv('INGEST_BEARER_TOKEN') ?: null;
        if (!$expectedToken) {
            $event->setResponse(ApiResponse::error(500, 'INGEST_BEARER_TOKEN is not set', $request->getPathInfo()));
            return;
        }

        $authHeader = (string) $request->headers->get('Authorization', '');
        if (!str_starts_with($authHeader, 'Bearer ')) {
            $event->setResponse(ApiResponse::error(401, 'Unauthorized', $request->getPathInfo()));
            return;
        }

        $providedToken = trim(substr($authHeader, strlen('Bearer ')));
        if ($providedToken === '' || !hash_equals((string) $expectedToken, $providedToken)) {
            $event->setResponse(ApiResponse::error(401, 'Unauthorized', $request->getPathInfo()));
            return;
        }

        $sourceSystem = $_SERVER['INGEST_SOURCE_SYSTEM'] ?? $_ENV['INGEST_SOURCE_SYSTEM'] ?? getenv('INGEST_SOURCE_SYSTEM') ?: 'default-source-system';
        $request->attributes->set('source_system', (string) $sourceSystem);
    }
}
