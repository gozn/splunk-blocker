.PHONY: up down logs ps verify

up:
	./scripts/start_all.sh

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

verify:
	curl -sS -o /tmp/splunk-blocker-dashboard.html -w '%{http_code} %{content_type}\n' http://127.0.0.1:$${HTTP_PORT:-4567}/dashboard/
	curl -sS http://127.0.0.1:$${HTTP_PORT:-4567}/active-blocks
