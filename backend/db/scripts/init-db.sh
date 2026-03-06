#!/bin/bash
set -e

echo "Initializing ProjectNexus database..."

# Run the SQL initialization script
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" < /docker-entrypoint-initdb.d/init.sql

echo "Database initialization complete!"
