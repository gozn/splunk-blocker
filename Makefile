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
	@dashboard_listen="$$(awk -F= '$$1=="DASHBOARD_LISTEN"{print substr($$0, index($$0, "=") + 1); exit}' .env 2>/dev/null)"; \
	dashboard_listen="$${dashboard_listen:-0.0.0.0:4567}"; \
	dashboard_listen="$${dashboard_listen%\"}"; dashboard_listen="$${dashboard_listen#\"}"; \
	dashboard_listen="$${dashboard_listen%\'}"; dashboard_listen="$${dashboard_listen#\'}"; \
	DASHBOARD_LISTEN="$$dashboard_listen"; \
	port="$${DASHBOARD_LISTEN##*:}"; port="$${port:-4567}"; \
	curl -sS -o /tmp/splunk-blocker-dashboard.html -w '%{http_code} %{content_type}\n' "http://127.0.0.1:$${port}/dashboard/"; \
	curl -sS "http://127.0.0.1:$${port}/active-blocks"
