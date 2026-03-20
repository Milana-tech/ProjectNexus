<?php

namespace App;

use Symfony\Bundle\FrameworkBundle\FrameworkBundle;
use Symfony\Bundle\FrameworkBundle\Kernel\MicroKernelTrait;
use Symfony\Component\Config\Loader\LoaderInterface;
use Symfony\Component\DependencyInjection\ContainerBuilder;
use Symfony\Component\DependencyInjection\Loader\Configurator\ContainerConfigurator;
use Symfony\Component\Routing\Loader\Configurator\RoutingConfigurator;
use Symfony\Component\HttpKernel\Kernel as BaseKernel;

class Kernel extends BaseKernel
{
    use MicroKernelTrait;

    public function registerBundles(): iterable
    {
        return [
            new FrameworkBundle(),
        ];
    }

    protected function configureContainer(ContainerConfigurator $container, LoaderInterface $loader): void
    {
        if ($this->environment === 'test') {
            $container->extension('framework', [
                'test' => true,
                'session' => [
                    'storage_factory_id' => 'session.storage.factory.mock_file',
                ],
            ]);
        }

        $services = $container->services();
        $services->defaults()
            ->autowire()
            ->autoconfigure();

        $services->load('App\\', dirname(__DIR__).'/src/')
            ->exclude(dirname(__DIR__).'/src/{Kernel.php}');
    }

    protected function configureRoutes(RoutingConfigurator $routes): void
    {
        $routes->import(dirname(__DIR__).'/src/Controller/', 'attribute');
    }
}
