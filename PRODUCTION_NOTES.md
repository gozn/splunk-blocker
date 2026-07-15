# Splunk Blocker Production Notes

## Production Model

Splunk and `splunk-blocker` run on the same Linux host.

```text
Firewall logs -> Splunk search/alert -> local webhook -> splunk-blocker -> Palo Alto API
```

The suspicious IP must come from firewall log fields in Splunk, not from the
splunk-blocker dashboard access log.

## Ports

Configured in `.env`:

```env
APP_BIND=127.0.0.1:6666
DASHBOARD_LISTEN=0.0.0.0:4567
WEBHOOK_LISTEN=127.0.0.1:6667
```

Meaning:

```text
127.0.0.1:6666  Flask/Gunicorn backend, local only
0.0.0.0:4567    Dashboard and read APIs for internal/VPN users
127.0.0.1:6667  Splunk webhook listener, local only
```

Production Splunk webhook URL:

```text
http://127.0.0.1:6667/webhook
```

Dashboard URL:

```text
http://<server-ip>:4567/dashboard/
```

Do not expose `6666` or `6667` externally.

## Splunk Alert Output

The webhook accepts a single IP:

```json
{"result": {"client_ip": "10.10.20.55"}}
```

or multiple IPs:

```json
{"result": {"values(client_ip)": ["10.10.20.55", "10.10.30.77"]}}
```

Example SPL:

```spl
index=firewall action=allowed threat="suspicious"
| stats count by src_ip
| where count >= 5
| rename src_ip as client_ip
```

If the alert aggregates several IPs:

```spl
index=firewall action=allowed threat="suspicious"
| stats count by src_ip
| where count >= 5
| stats values(src_ip) as client_ip
```

## Deploy

```bash
cd ~/Desktop/splunk-blocker
docker compose down
docker compose up -d --force-recreate --build
```

## Verify

Expected listeners:

```text
127.0.0.1:6666
0.0.0.0:4567
127.0.0.1:6667
```

Commands:

```bash
ss -ltnp | grep -E ':4567|:6667|:6666'
curl -I http://127.0.0.1:4567/dashboard/
curl -X POST http://127.0.0.1:6667/webhook \
  -H 'Content-Type: application/json' \
  -d '{"search_name":"verify","result":{"client_ip":"192.0.2.10"}}'
```

After a Splunk alert fires:

```bash
tail -n 5 logs/alerts/splunk_alerts.log
curl http://127.0.0.1:4567/active-blocks
```

## Lab Notes

The `dummy0` target and static route tricks are lab-only. They were used to
generate traffic through PAN-OS without running another VM.

Do not carry those host routes into production. Production should block the IPs
reported by firewall logs in Splunk.

## Files

```text
docker-compose.yml              Docker services, host networking, env-driven Nginx
docker/nginx.conf.template      Dashboard listener, local-only webhook listener, backend proxy target
app/routes.py                   Webhook parsing; supports one or many client IPs
.env.example                    Runtime variables template
.env                            Local secrets/runtime config, not committed
```
