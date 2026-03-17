<?php

namespace App\EventSubscriber;

use App\Security\AdminJwt;
use Symfony\Component\EventDispatcher\Attribute\AsEventListener;
use Symfony\Component\HttpKernel\Event\RequestEvent;
use Symfony\Component\HttpKernel\KernelEvents;
use Symfony\Component\HttpFoundation\JsonResponse;

final class AdminProtectionSubscriber
{
    #[AsEventListener(event: KernelEvents::REQUEST, priority: 100)]
    public function onKernelRequest(RequestEvent $event): void
    {
        $request = $event->getRequest();

        if (strtoupper($request->getMethod()) !== 'POST') {
            return;
        }

        $path = $request->getPathInfo();
        if ($path !== '/entity-types' && $path !== '/metrics') {
            return;
        }

        try {
            AdminJwt::assertAdmin($request);
        } catch (\Throwable $e) {
            $event->setResponse(new JsonResponse(['error' => 'Forbidden'], 403));
        }
    }
}
