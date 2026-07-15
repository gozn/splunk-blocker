#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

cd "$PROJECT_ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
    cp .env.example "$ENV_FILE"
    echo "Created .env from .env.example. Set PALO_ALTO_URL before enabling firewall API actions."
fi

read_env_value() {
    local key="$1"
    local value

    value="$(awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1); exit}' "$ENV_FILE")"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    printf '%s' "$value"
}

APP_BIND="$(read_env_value APP_BIND)"
DASHBOARD_LISTEN="$(read_env_value DASHBOARD_LISTEN)"
WEBHOOK_LISTEN="$(read_env_value WEBHOOK_LISTEN)"

APP_BIND="${APP_BIND:-127.0.0.1:6666}"
DASHBOARD_LISTEN="${DASHBOARD_LISTEN:-0.0.0.0:4567}"
WEBHOOK_LISTEN="${WEBHOOK_LISTEN:-127.0.0.1:6667}"

if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    echo "ERROR: Docker Compose is not installed." >&2
    exit 1
fi

"${COMPOSE[@]}" up -d --build

dashboard_port="${DASHBOARD_LISTEN##*:}"
webhook_host="${WEBHOOK_LISTEN%:*}"
webhook_port="${WEBHOOK_LISTEN##*:}"

echo "SOC portal is starting on http://127.0.0.1:${dashboard_port}/"
echo "Dashboard: http://127.0.0.1:${dashboard_port}/dashboard/"
echo "Splunk webhook: http://${webhook_host}:${webhook_port}/webhook"
echo "Backend bind: ${APP_BIND}"
