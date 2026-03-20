FROM php:8.3-cli

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git unzip libpq-dev \
    && docker-php-ext-install pdo_pgsql \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

ENV COMPOSER_ALLOW_SUPERUSER=1

ARG INSTALL_DEV_DEPS=1

COPY composer.json ./

RUN if [ "$INSTALL_DEV_DEPS" = "0" ]; then \
        composer install --no-dev --no-interaction --no-progress --prefer-dist; \
    else \
        composer install --no-interaction --no-progress --prefer-dist; \
    fi

COPY . .

RUN composer dump-autoload --optimize

EXPOSE 8000

CMD ["php", "-S", "0.0.0.0:8000", "-t", "public"]
