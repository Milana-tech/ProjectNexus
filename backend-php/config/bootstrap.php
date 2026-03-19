<?php

use Symfony\Component\Dotenv\Dotenv;

require dirname(__DIR__).'/vendor/autoload.php';

$appEnv = $_SERVER['APP_ENV'] ?? $_ENV['APP_ENV'] ?? getenv('APP_ENV') ?: null;
$appDebug = $_SERVER['APP_DEBUG'] ?? $_ENV['APP_DEBUG'] ?? getenv('APP_DEBUG') ?: null;

if ($appEnv !== null && $appEnv !== '') {
    $_SERVER['APP_ENV'] = $_ENV['APP_ENV'] = $appEnv;
    if ($appDebug !== null && $appDebug !== '') {
        $_SERVER['APP_DEBUG'] = $_ENV['APP_DEBUG'] = $appDebug;
    }
} else {
    $envFile = dirname(__DIR__).'/.env';

    if (is_file($envFile)) {
        (new Dotenv())->bootEnv($envFile);
    } else {
        $_SERVER['APP_ENV'] = $_ENV['APP_ENV'] = 'dev';
        $_SERVER['APP_DEBUG'] = $_ENV['APP_DEBUG'] = '1';
    }
}
