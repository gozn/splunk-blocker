import os
from pathlib import Path


PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT / "db" / "splunk_blocker.db"))
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "/opt/nginx-logs/splunk_alerts.log")

PALO_ALTO_URL = os.getenv("PALO_ALTO_URL", "")
PALO_ALTO_VERIFY_SSL = os.getenv("PALO_ALTO_VERIFY_SSL", "false").lower() == "true"
