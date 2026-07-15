#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

cd "$PROJECT_ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
    cp .env.example "$ENV_FILE"
    echo "Created .env from .env.example. Set PALO_ALTO_URL before enabling firewall API actions."
fi

if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    echo "ERROR: Docker Compose is not installed." >&2
    exit 1
fi

"${COMPOSE[@]}" up -d --build

echo "SOC portal is starting on http://127.0.0.1:${HTTP_PORT:-4567}/"
echo "Dashboard: http://127.0.0.1:${HTTP_PORT:-4567}/dashboard/"
