import sqlite3
import json
from datetime import datetime, timedelta
from config.settings import DB_PATH
from app.firewall import block_ip, unblock_ip

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database and create tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table for storing individual violations/alerts
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip TEXT NOT NULL,
            rule_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            payload TEXT
        )
        """
    )

    # Table for storing active and historical IP block actions
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ip_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip TEXT NOT NULL,
            block_start TEXT NOT NULL,
            block_end TEXT NOT NULL,
            violation_count INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    # Table for recording manual unblock actions (audit trail)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS unblock_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip    TEXT NOT NULL,
            unblocked_at TEXT NOT NULL,
            reason       TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()

def count_recent_blocks(client_ip, days=7):
    """Count how many blocks this IP has had whose start time is within the last `days` days."""
    now = datetime.utcnow()
    recent_start = (now - timedelta(days=days)).isoformat() + "Z"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM ip_blocks WHERE client_ip = ? AND block_start >= ?",
        (client_ip, recent_start)
    )
    recent_count = cursor.fetchone()[0]
    conn.close()
    return recent_count

def record_violation(client_ip, rule_name, raw_payload):
    """Record a violation and create a progressive block."""
    now = datetime.utcnow()
    now_str = now.isoformat() + "Z"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Store the violation record
    cursor.execute(
        "INSERT INTO violations (client_ip, rule_name, timestamp, payload) VALUES (?, ?, ?, ?)",
        (client_ip, rule_name, now_str, json.dumps(raw_payload))
    )

    # Do not create a new block if an active one already exists
    cursor.execute(
        "SELECT COUNT(*) FROM ip_blocks WHERE client_ip = ? AND block_end > ?",
        (client_ip, now_str)
    )
    if cursor.fetchone()[0] > 0:
        conn.commit()
        conn.close()
        return None

    recent_blocks = count_recent_blocks(client_ip, days=7)
    violation_count = recent_blocks + 1  # tier index

    if violation_count == 1:
        duration_minutes = 5
    elif violation_count == 2:
        duration_minutes = 30
    else:
        duration_minutes = 10080  # 7 days

    block_end = now + timedelta(minutes=duration_minutes)
    block_end_str = block_end.isoformat() + "Z"
    reason = f"Triggered rule: '{rule_name}' (Violation #{violation_count})"

    cursor.execute(
        "INSERT INTO ip_blocks (client_ip, block_start, block_end, violation_count, reason, status) VALUES (?, ?, ?, ?, ?, ?)",
        (client_ip, now_str, block_end_str, violation_count, reason, "ACTIVE")
    )

    conn.commit()
    conn.close()

    # Real-time blocking on Palo Alto Firewall
    block_ip(client_ip, duration_minutes)

    return {
        "client_ip": client_ip,
        "block_start": now_str,
        "block_end": block_end_str,
        "violation_count": violation_count,
        "duration_minutes": duration_minutes,
        "reason": reason,
    }

def get_active_blocks():
    """Return a list of currently active IP blocks (block_end in the future)."""
    now_str = datetime.utcnow().isoformat() + "Z"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT client_ip, block_start, block_end, violation_count, reason FROM ip_blocks WHERE block_end > ? ORDER BY block_start DESC",
        (now_str,)
    )
    rows = cursor.fetchall()
    conn.close()
    blocks = []
    for row in rows:
        blocks.append({
            "client_ip": row["client_ip"],
            "block_start": row["block_start"],
            "block_end": row["block_end"],
            "violation_count": row["violation_count"],
            "reason": row["reason"],
        })
    return blocks

def unblock_ip_db(client_ip, reason="Manual unblock by operator"):
    """Expire all active blocks for the given IP in DB and call Palo Alto unblock API."""
    now_str = datetime.utcnow().isoformat() + "Z"
    conn = get_db_connection()
    cursor = conn.cursor()

    # Expire active blocks
    cursor.execute(
        "UPDATE ip_blocks SET block_end = ? WHERE client_ip = ? AND block_end > ?",
        (now_str, client_ip, now_str)
    )
    affected = cursor.rowcount

    if affected > 0:
        # Record the unblock event for audit purposes
        cursor.execute(
            "INSERT INTO unblock_events (client_ip, unblocked_at, reason) VALUES (?, ?, ?)",
            (client_ip, now_str, reason)
        )

    conn.commit()
    conn.close()

    if affected > 0:
        # Real-time unblocking/unregistering on Palo Alto Firewall
        unblock_ip(client_ip)

    return affected

def get_ip_block_history(client_ip):
    """Return all block records + unblock events for a given IP, merged and sorted by time."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT block_start, block_end, violation_count, reason FROM ip_blocks WHERE client_ip = ? ORDER BY block_start DESC",
        (client_ip,)
    )
    blocks = []
    for row in cursor.fetchall():
        now_str = datetime.utcnow().isoformat() + "Z"
        blocks.append({
            "type": "block",
            "client_ip": client_ip,
            "block_start": row["block_start"],
            "block_end": row["block_end"],
            "violation_count": row["violation_count"],
            "reason": row["reason"],
            "status": "ACTIVE" if row["block_end"] > now_str else "EXPIRED",
        })

    cursor.execute(
        "SELECT unblocked_at, reason FROM unblock_events WHERE client_ip = ? ORDER BY unblocked_at DESC",
        (client_ip,)
    )
    unblocks = []
    for row in cursor.fetchall():
        unblocks.append({
            "type": "unblock",
            "client_ip": client_ip,
            "unblocked_at": row["unblocked_at"],
            "reason": row["reason"],
        })

    conn.close()
    return {"blocks": blocks, "unblocks": unblocks}

def get_all_violations():
    """Return a list of all logged violations."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, client_ip, rule_name, timestamp FROM violations ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    violations = []
    for row in rows:
        violations.append({
            "id": row["id"],
            "client_ip": row["client_ip"],
            "rule_name": row["rule_name"],
            "timestamp": row["timestamp"],
        })
    return violations

def get_total_block_count(client_ip):
    """Return the total number of block records ever created for the given IP."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ip_blocks WHERE client_ip = ?", (client_ip,))
    total = cursor.fetchone()[0]
    conn.close()
    return total
