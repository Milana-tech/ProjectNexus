#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR"

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example"
fi

echo "Starting Project Nexus stack..."
docker compose up --build -d

echo "\nWaiting for services to become healthy..."
docker compose ps

echo "\nURLs:"
echo "- FastAPI:       http://localhost:8000/health"
echo "- Frontend:      http://localhost:3000"
echo "- PHP backend:   http://localhost:8001/health"

echo "\nTip: to stop: docker compose down"
