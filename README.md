# SOC-Portal: Landing Page, Logging & progressive IP Blocker Setup Guide

This repository contains a Security Operations Center (SOC) Operations Portal landing page hosted on Nginx, optimized to output structured JSON logs, and a Python Flask Webhook receiver integrated with an SQLite database to automate progressive IP blocking when alerts are triggered by Splunk.

---

## 1. System Requirements

Ensure the target system meets the following software requirements:
- **Operating System**: Linux (Ubuntu/Debian, CentOS/RHEL, or similar)
- **Web Server**: `nginx` (v1.18+)
- **Runtime Environment**: Python 3.8+ (with `venv` support)
- **Network Access**: Port `4567` (for Nginx) must be open. Port `6666` (for Flask Webhook) runs on localhost and is proxied through Nginx.

### Recommended production path

For production or repeatable deployment, use the Docker Compose packaging instead of the manual Nginx + venv flow.

```bash
./scripts/start_all.sh
```

This creates `.env` from `.env.example` if missing, builds the Flask/Gunicorn app image, starts Nginx, persists SQLite data under `./db`, writes Nginx logs under `./logs/nginx`, writes webhook alert logs under `./logs/alerts`, and exposes:

```text
SOC Portal: http://127.0.0.1:4567/
Dashboard : http://127.0.0.1:4567/dashboard/
Webhook   : http://127.0.0.1:4567/webhook
```

Set firewall integration values in `.env` before using Palo Alto actions:

```bash
PALO_ALTO_URL='https://<firewall>/api/?type=user-id&key=<api-key>'
PALO_ALTO_VERIFY_SSL=false
```

Common operations:

```bash
make up
make ps
make logs
make verify
make down
```

---

## 2. Directory Structure Setup

Before running the server, the system log directory must exist and be writable by the user running Nginx and Python. Run these commands:

```bash
# Create the directory for logs and pid file
sudo mkdir -p /opt/nginx-logs

# Grant ownership to the current user (replace tritc with your deploy user if different)
sudo chown -R tritc:tritc /opt/nginx-logs
```

### Folder Layout Reference
```
splunk-blocker/
├── run.py                  # Entrypoint script to launch Flask
├── requirements.txt        # Python package dependencies
├── app/                    # Main application package
│   ├── __init__.py         # Flask App Factory & database setup
│   ├── routes.py           # HTTP handlers (Webhook receiver, APIs, Dashboard view)
│   ├── database.py         # SQLite CRUD queries & interactions
│   ├── firewall.py         # Palo Alto Firewall API wrapper
│   └── templates/
│       └── dashboard.html  # Dashboard UI template (Jinja2)
├── config/
│   ├── settings.py         # Runtime settings loaded from environment variables
│   └── nginx.conf          # Nginx server configuration (Reverse Proxy & Landing Web Server)
├── db/
│   └── splunk_blocker.db   # Persistent SQLite Database file
├── public/                 # Static web files served by Nginx (Landing page)
│   ├── index.html          # SOC-Portal page layout
│   ├── style.css           # Glassmorphism styling and scan animations
│   └── app.js              # Clock, metric fluctuation and API trigger logic
├── scripts/                # Utility scripts for operations
│   ├── start_flask.sh      # Shell script wrapper to start Flask in background
│   └── seed_sample_data.py # Script to populate mock alerts/blocks history
└── venv/                   # Python virtual environment (created locally)
```

### Current Operational File Locations

The operational files currently live under `config/` and `scripts/`.
There are no root-level `nginx.conf`, `start_flask.sh`, or `seed_sample_data.py`
files in the current project layout.

Use these paths:

```bash
# Nginx config
/home/tritc/Desktop/splunk-blocker/config/nginx.conf

# Start Flask
/home/tritc/Desktop/splunk-blocker/scripts/start_flask.sh

# Seed sample dashboard data
/home/tritc/Desktop/splunk-blocker/scripts/seed_sample_data.py
```

---

## 3. Web Server & Reverse Proxy Deployment (Nginx)

Nginx is configured to serve both the static landing page on port `4567` and act as a **Reverse Proxy** to forward dashboard and webhook requests to the Flask server (port `6666`). This bypasses virtualization or local firewall restrictions that block port `6666`.

### Configured Proxy Routes:
- `/dashboard/` -> Proxied to Flask `GET /` (Serves the GUI Dashboard)
- `/active-blocks` -> Proxied to Flask `GET /active-blocks`
- `/violations` -> Proxied to Flask `GET /violations`
- `/webhook` -> Proxied to Flask `POST /webhook`
- `/unblock/` -> Proxied to Flask `POST /unblock/<ip>`
- `/history/` -> Proxied to Flask `GET /history/<ip>`

### Steps:
1. Review the root path in [nginx.conf](file:///home/tritc/Desktop/splunk-blocker/config/nginx.conf):
   ```nginx
   root /home/tritc/Desktop/splunk-blocker/public;
   ```
   *Make sure this absolute path points to the directory where your public folder resides.*
2. Start Nginx:
   ```bash
   nginx -c /home/tritc/Desktop/splunk-blocker/config/nginx.conf
   ```
3. Stop Nginx:
   ```bash
   nginx -s stop -c /home/tritc/Desktop/splunk-blocker/config/nginx.conf
   ```
4. Reload Nginx configuration without restarting:
   ```bash
   nginx -s reload -c /home/tritc/Desktop/splunk-blocker/config/nginx.conf
   ```
5. Verification:
   - View SOC-Portal: `http://<server-ip>:4567/`
   - View Web GUI Dashboard: `http://<server-ip>:4567/dashboard/`

### Runtime Verification

After starting both services, verify:

```bash
ss -ltnp
curl -sS -o /tmp/splunk-blocker-dashboard.html -w '%{http_code} %{content_type}\n' http://127.0.0.1:4567/dashboard/
curl -sS http://127.0.0.1:4567/active-blocks
```

Expected listeners:

```text
Nginx: 0.0.0.0:4567
Flask: 0.0.0.0:6666
```

---

## 4. Webhook Server Setup (Python Flask)

The webhook receiver accepts Splunk alert payloads, parses client IPs, records violations in SQLite, and tracks block durations. All settings (such as target DB path and Palo Alto URL/Keys) are defined in `config/settings.py`.

### Steps:
1. Create a Python Virtual Environment inside the project root:
   ```bash
   python3 -m venv venv
   ```
2. Install dependencies:
   ```bash
   venv/bin/pip install -r requirements.txt
   ```
3. Start the Webhook server:
   ```bash
   ./scripts/start_flask.sh
   ```
   *The server runs locally in the background on port 6666 and prints logs to flask.log.*

4. Stop the Webhook server:
   ```bash
   pkill -f "/home/tritc/Desktop/splunk-blocker/venv/bin/python -u run.py"
   ```

---

## 5. Splunk Integration Guide

### Step 1: Log Ingestion (Nginx JSON logs)
For Docker Compose deployments, configure your Splunk Universal Forwarder to monitor `./logs/nginx/access.log` from the project directory.

For manual Nginx deployments, monitor `/opt/nginx-logs/access.log`.

Example manual input:
- **`inputs.conf`**:
  ```ini
  [monitor:///opt/nginx-logs/access.log]
  disabled = false
  index = security_logs
  sourcetype = _json
  ```
Splunk will automatically index and parse all parameters (`client_ip`, `status`, `request_uri`, `soc_event_type`) without requiring custom regular expressions.

### Step 2: Creating Alerts & Webhook Triggers
1. Write a Splunk search query to detect malicious activity (e.g. brute force, anomalies, or test triggers):
   ```splunk
   index=security_logs status=403 soc_event_type="simulate-intrusion"
   | stats count by client_ip
   | where count > 3
   ```
2. Save this search as an **Alert**.
3. Set **Trigger Actions** -> Add Action -> **Webhook**.
4. Configure the Webhook URL (pointing to the Nginx port):
   ```
   http://<your-server-ip>:4567/webhook
   ```
   *Requests sent to Nginx will be proxied automatically to the Flask backend, logging the webhook activity in Nginx logs simultaneously.*

### Step 3: Gateway Block Enforcement
Your firewall or routing scripts can query the active blocks list to block malicious IPs:
```bash
# Query the Nginx proxy endpoint to fetch currently blocked IPs
curl http://<your-server-ip>:4567/active-blocks
```
Output schema:
```json
{
  "active_blocks": [
    {
      "client_ip": "198.51.100.42",
      "violation_count": 3,
      "reason": "Triggered rule: 'Third Violation Alert' (Violation #3)",
      "block_start": "2026-07-02T15:37:52.088055Z",
      "block_end": "2026-07-09T15:37:52.088055Z"
    }
  ],
  "active_blocks_count": 1,
  "status": "success"
}
```
Use this JSON data in your automation playbooks (e.g., Ansible, IPtables, or cloud security groups) to block traffic from those IPs.

---

## 6. Seeding Sample Data

To populate the database with mock violations and block history for testing the dashboard:
```bash
python scripts/seed_sample_data.py
```

---

## 7. Manual Unblock & IP History APIs

### Unblock an IP Address
To manually unblock an IP address (which expires all active block records for that IP in the database and calls the firewall's unblock API):
- **Endpoint**: `POST /unblock/<ip>`
- **Payload (JSON, optional)**:
  ```json
  {
    "reason": "False positive / approved whitelist"
  }
  ```
- **Example Request**:
  ```bash
  curl -X POST -H "Content-Type: application/json" -d '{"reason": "Testing manual unblock"}' http://localhost:4567/unblock/10.0.0.1
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "message": "Unblocked 10.0.0.1",
    "blocks_removed": 1
  }
  ```

### Retrieve IP Block History
To get the complete history of blocks and manual unblock events for a specific IP:
- **Endpoint**: `GET /history/<ip>`
- **Example Request**:
  ```bash
  curl http://localhost:4567/history/10.0.0.1
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "history": {
      "blocks": [
        {
          "block_end": "2026-07-08T07:40:00.000000Z",
          "block_start": "2026-07-08T07:35:00.000000Z",
          "reason": "Triggered rule: 'Brute Force Login Attempt' (Violation #1)",
          "status": "EXPIRED",
          "timestamp": "2026-07-08T07:35:00.000000Z",
          "type": "block",
          "violation_count": 1
        }
      ],
      "unblocks": [
        {
          "reason": "Testing manual unblock",
          "type": "unblock",
          "unblocked_at": "2026-07-08T07:36:12.000000Z"
        }
      ]
    }
  }
  ```
