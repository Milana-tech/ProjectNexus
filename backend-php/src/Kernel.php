<?php

namespace App;

use Symfony\Bundle\FrameworkBundle\Kernel\MicroKernelTrait;
use Symfony\Component\DependencyInjection\Loader\Configurator\ContainerConfigurator;
use Symfony\Component\HttpKernel\Kernel as BaseKernel;
use Symfony\Component\Routing\Loader\Configurator\RoutingConfigurator;

class Kernel extends BaseKernel
{
    use MicroKernelTrait;

    protected function configureContainer(ContainerConfigurator $container): void
    {
        $container->services()
            ->defaults()
                ->autowire()
                ->autoconfigure();

        $container->services()
            ->load('App\\', '../src/')
            ->exclude('../src/Kernel.php');
    }

    protected function configureRoutes(RoutingConfigurator $routes): void
    {
        $routes->import('../src/Controller/', 'attribute');
    }
}
