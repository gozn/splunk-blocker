#!/usr/bin/env bash
# start_flask.sh – start only the Flask webhook server (nginx is assumed to be already running)
# Place in scripts/ and run ./scripts/start_flask.sh
# The script:
#   1. Sources an existing virtual‑env (if present).
#   2. Starts Flask in background using run.py and prints its PID and log file.
#   3. Exits without stopping anything, so an already‑running nginx stays up.

set -euo pipefail

# Resolve PROJECT_ROOT to the parent of the scripts folder
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$PROJECT_ROOT/venv"
FLASK_SCRIPT="$PROJECT_ROOT/run.py"
FLASK_LOG="$PROJECT_ROOT/flask.log"

# ---- Determine Python binary to use -----------------------------------------
if [[ -f "$VENV/bin/python" ]]; then
    PYTHON_EXEC="$VENV/bin/python"
else
    echo "WARNING: virtual‑env python not found – assuming system python."
    PYTHON_EXEC="python"
fi

# ---- Start Flask -----------------------------------------------------------
echo "Starting Flask server…"
cd "$PROJECT_ROOT"
nohup "$PYTHON_EXEC" -u "$FLASK_SCRIPT" > "$FLASK_LOG" 2>&1 &
FLASK_PID=$!
disown

echo "Flask PID: $FLASK_PID (log: $FLASK_LOG)"

echo "✅ Flask is running. Access the dashboard via the existing Nginx proxy at http://<your-host-ip>:4567/dashboard/"
