<?php

use App\Kernel;

if (!isset($_SERVER['APP_ENV']) && ($appEnv = getenv('APP_ENV')) !== false && $appEnv !== '') {
    $_SERVER['APP_ENV'] = $_ENV['APP_ENV'] = $appEnv;
}

if (!isset($_SERVER['APP_DEBUG']) && ($appDebug = getenv('APP_DEBUG')) !== false && $appDebug !== '') {
    $_SERVER['APP_DEBUG'] = $_ENV['APP_DEBUG'] = $appDebug;
}

if (!isset($_SERVER['APP_RUNTIME_OPTIONS'])) {
    $_SERVER['APP_RUNTIME_OPTIONS'] = $_ENV['APP_RUNTIME_OPTIONS'] = [
        'disable_dotenv' => true,
    ];
}

require_once dirname(__DIR__).'/vendor/autoload_runtime.php';

return function (array $context) {
    return new Kernel($context['APP_ENV'], (bool) $context['APP_DEBUG']);
};
