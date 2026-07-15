"""
seed_sample_data.py – Insert sample violations + block history for testing the dashboard.
Run from project root: python scripts/seed_sample_data.py
"""
import sys, os
# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
import json
from datetime import datetime, timedelta
from config.settings import DB_PATH

CASES = [
    # IP 1: New offender – first violation 1 min ago, 5m block → ACTIVE
    {
        "ip": "10.0.0.1",
        "rule": "Brute Force Login Attempt",
        "events": [
            {"minutes_ago": 1, "block_duration_minutes": 5, "tier": 1},
        ]
    },
    # IP 2: Repeat offender – tier 2 (30m block) started 5 mins ago → ACTIVE
    {
        "ip": "10.0.0.2",
        "rule": "SQL Injection Probe",
        "events": [
            {"minutes_ago": 60 * 24 * 3, "block_duration_minutes": 5,  "tier": 1},  # 3 days ago, expired
            {"minutes_ago": 5,           "block_duration_minutes": 30, "tier": 2},  # 5 mins ago, ACTIVE
        ]
    },
    # IP 3: Hardcore repeat – tier 3 (7d block) started 2 days ago → ACTIVE
    {
        "ip": "192.168.1.99",
        "rule": "Credential Stuffing Alert",
        "events": [
            {"minutes_ago": 60 * 24 * 6, "block_duration_minutes": 5,    "tier": 1},  # 6 days ago, expired
            {"minutes_ago": 60 * 24 * 4, "block_duration_minutes": 30,   "tier": 2},  # 4 days ago, expired
            {"minutes_ago": 60 * 24 * 2, "block_duration_minutes": 10080,"tier": 3},  # 2 days ago, ACTIVE (7d)
        ]
    },
    # IP 4: Reset after 7-day window – tier 1 again (5m block), started 2 mins ago → ACTIVE
    {
        "ip": "172.16.0.50",
        "rule": "Port Scan Detected",
        "events": [
            {"minutes_ago": 60 * 24 * 10, "block_duration_minutes": 5,  "tier": 1},  # 10 days ago, expired
            {"minutes_ago": 60 * 24 * 9,  "block_duration_minutes": 30, "tier": 2},  # 9 days ago, expired
            {"minutes_ago": 2,            "block_duration_minutes": 5,  "tier": 1},  # reset, ACTIVE
        ]
    },
    # IP 5: All blocks expired – history only
    {
        "ip": "203.0.113.7",
        "rule": "XSS Payload Detected",
        "events": [
            {"minutes_ago": 60 * 24 * 14, "block_duration_minutes": 5,  "tier": 1},  # 14 days ago, expired
            {"minutes_ago": 60 * 24 * 13, "block_duration_minutes": 30, "tier": 2},  # 13 days ago, expired
        ]
    },
    # IP 6: Extra case – mid-tier block 10 mins ago
    {
        "ip": "198.51.100.77",
        "rule": "Directory Traversal Attempt",
        "events": [
            {"minutes_ago": 60 * 24 * 2,  "block_duration_minutes": 5,  "tier": 1},  # 2 days ago, expired
            {"minutes_ago": 10,            "block_duration_minutes": 30, "tier": 2},  # 10 mins ago, ACTIVE
        ]
    },
    # IP 7: Historical only – old DDoS attempt
    {
        "ip": "45.33.32.156",
        "rule": "DDoS Rate Limit Exceeded",
        "events": [
            {"minutes_ago": 60 * 24 * 20, "block_duration_minutes": 5,    "tier": 1},
            {"minutes_ago": 60 * 24 * 18, "block_duration_minutes": 30,   "tier": 2},
            {"minutes_ago": 60 * 24 * 15, "block_duration_minutes": 10080,"tier": 3},  # expired 8 days ago
        ]
    },
]

def run():
    # Ensure db directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure tables exist
    c.execute("""CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_ip TEXT NOT NULL,
        rule_name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        payload TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS ip_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_ip TEXT NOT NULL,
        block_start TEXT NOT NULL,
        block_end TEXT NOT NULL,
        violation_count INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL
    )""")

    now = datetime.utcnow()
    total_violations = 0
    total_blocks = 0

    for case in CASES:
        ip = case["ip"]
        rule = case["rule"]
        for event in case["events"]:
            ts = now - timedelta(minutes=event["minutes_ago"])
            block_start = ts
            block_end = ts + timedelta(minutes=event["block_duration_minutes"])
            tier = event["tier"]
            reason = f"Triggered rule: '{rule}' (Violation #{tier})"
            status = "ACTIVE" if block_end > now else "EXPIRED"

            payload = json.dumps({"search_name": rule, "result": {"client_ip": ip}})

            c.execute("INSERT INTO violations (client_ip, rule_name, timestamp, payload) VALUES (?, ?, ?, ?)",
                      (ip, rule, ts.isoformat() + "Z", payload))
            c.execute("INSERT INTO ip_blocks (client_ip, block_start, block_end, violation_count, reason, status) VALUES (?, ?, ?, ?, ?, ?)",
                      (ip, block_start.isoformat() + "Z", block_end.isoformat() + "Z", tier, reason, status))
            total_violations += 1
            total_blocks += 1

    conn.commit()
    conn.close()

    print(f"✅ Seeded {total_violations} violations and {total_blocks} block records.")
    print("IPs seeded:")
    for case in CASES:
        print(f"  • {case['ip']:20s} – {len(case['events'])} event(s)  [{case['rule']}]")

if __name__ == "__main__":
    run()
