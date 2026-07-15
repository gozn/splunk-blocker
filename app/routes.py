from flask import Blueprint, request, jsonify, render_template
import logging
import json
import os
import ipaddress
from datetime import datetime
from config.settings import LOG_FILE_PATH
from app.database import (
    record_violation, get_active_blocks, get_all_violations,
    unblock_ip_db, get_ip_block_history
)

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

# ANSI Color Codes for premium terminal styling
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
RESET = '\033[0m'

def _flatten_ip_values(value):
    if value is None:
        return []
    if isinstance(value, list):
        items = []
        for item in value:
            items.extend(_flatten_ip_values(item))
        return items
    if isinstance(value, str):
        parts = []
        for item in value.split(','):
            item = item.strip()
            if item:
                parts.append(item)
        return parts
    return [str(value).strip()]

def extract_client_ips(result):
    """Extract one or more client IPs from Splunk webhook result fields."""
    candidates = []
    candidates.extend(_flatten_ip_values(result.get('client_ip')))
    candidates.extend(_flatten_ip_values(result.get('values(client_ip)')))

    ips = []
    seen = set()
    for candidate in candidates:
        try:
            ip = str(ipaddress.ip_address(candidate))
        except ValueError:
            logger.warning("Skipping invalid client_ip value from webhook payload: %s", candidate)
            continue
        if ip not in seen:
            ips.append(ip)
            seen.add(ip)
    return ips

@main_bp.route('/webhook', methods=['POST'])
def splunk_webhook():
    # Verify content type
    if not request.is_json:
        logger.warning("Received webhook request with non-JSON content type")
        return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400

    try:
        payload = request.get_json()
    except Exception as e:
        logger.error(f"Failed to parse incoming JSON: {e}")
        return jsonify({"status": "error", "message": "Invalid JSON structure"}), 400

    # Extract Splunk Alert Metadata
    search_name = payload.get('search_name', 'Unknown Alert')
    sid = payload.get('sid', 'N/A')
    app_name = payload.get('app', 'N/A')
    owner = payload.get('owner', 'N/A')
    results_link = payload.get('results_link', 'N/A')
    result = payload.get('result', {})

    # 1. Write the alert payload persistently to the log file (JSON format)
    try:
        log_entry = {
            "received_at": datetime.utcnow().isoformat() + "Z",
            "search_name": search_name,
            "sid": sid,
            "app": app_name,
            "owner": owner,
            "results_link": results_link,
            "result": result
        }
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write alert to log file: {e}")

    # 2. Extract Client IPs – Splunk may send 'client_ip' or 'values(client_ip)' as a string or list
    client_ips = extract_client_ips(result)
    block_results = []
    skipped_ips = []
    if client_ips:
        for client_ip in client_ips:
            try:
                block_info = record_violation(client_ip, search_name, payload)
                if block_info:
                    block_results.append(block_info)
                else:
                    skipped_ips.append({
                        "client_ip": client_ip,
                        "reason": "active block already exists"
                    })
            except Exception as e:
                logger.error(f"Database operation failed for {client_ip}: {e}")
                skipped_ips.append({
                    "client_ip": client_ip,
                    "reason": str(e)
                })
    else:
        logger.warning("No client_ip found in Splunk result payload; skipping block calculation")

    # 3. Display a premium-styled banner in the console
    print(f"\n{RED}{BOLD}=" * 60)
    print(f"🚨 SPLUNK ALERT TRIGGERED 🚨")
    print(f"=" * 60 + RESET)
    print(f"{BOLD}Alert Name  :{RESET} {YELLOW}{search_name}{RESET}")
    print(f"{BOLD}Search ID   :{RESET} {sid}")
    print(f"{BOLD}Splunk App  :{RESET} {app_name}")
    print(f"{BOLD}Owner       :{RESET} {owner}")
    print(f"{BOLD}Results Link:{RESET} {CYAN}{results_link}{RESET}")
    
    if result:
        print(f"\n{GREEN}{BOLD}--- ALERT DATA DETAILS ---{RESET}")
        for key, val in result.items():
            print(f"  • {BOLD}{key:<15}:{RESET} {val}")
    else:
        print(f"\n{YELLOW}[No inline result data provided in this alert payload]{RESET}")

    # 4. Display progressive IP blocking details if triggered
    if block_results:
        print(f"\n{RED}{BOLD}🚫 IP BLOCK EXECUTED 🚫{RESET}")
        for block_info in block_results:
            print(f"  • {BOLD}Blocked IP    :{RESET} {RED}{block_info['client_ip']}{RESET}")
            print(f"    {BOLD}Duration      :{RESET} {YELLOW}{block_info['duration_minutes']} minutes{RESET} (Violation #{block_info['violation_count']})")
            print(f"    {BOLD}Block Period  :{RESET} {block_info['block_start']} to {block_info['block_end']}")
            print(f"    {BOLD}Block Reason  :{RESET} {block_info['reason']}")
        
    print(f"{RED}{BOLD}=" * 60 + RESET + "\n")

    response_data = {
        "status": "success",
        "message": "Webhook alert processed successfully",
        "alert_name": search_name,
        "client_ips": client_ips,
        "blocks_created": len(block_results),
        "blocks_skipped": len(skipped_ips),
    }
    if block_results:
        response_data["block_results"] = block_results
    if skipped_ips:
        response_data["skipped_ips"] = skipped_ips

    return jsonify(response_data), 200

@main_bp.route('/active-blocks', methods=['GET'])
def active_blocks():
    """Query currently active IP blocks."""
    try:
        blocks = get_active_blocks()
        return jsonify({
            "status": "success",
            "active_blocks_count": len(blocks),
            "active_blocks": blocks
        }), 200
    except Exception as e:
        logger.error(f"Failed to query active blocks: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@main_bp.route('/unblock/<ip>', methods=['POST'])
def unblock_ip(ip):
    """Manually expire all active blocks for a given IP and record the reason."""
    body = request.get_json(silent=True) or {}
    reason = body.get('reason', 'Manual unblock by operator').strip() or 'Manual unblock by operator'
    try:
        affected = unblock_ip_db(ip, reason)
        if affected > 0:
            logger.info(f"Manually unblocked IP: {ip} | reason: {reason}")
            return jsonify({"status": "success", "message": f"Unblocked {ip}", "blocks_removed": affected}), 200
        else:
            return jsonify({"status": "not_found", "message": f"No active blocks found for {ip}"}), 404
    except Exception as e:
        logger.error(f"Failed to unblock {ip}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@main_bp.route('/violations', methods=['GET'])
def list_violations():
    """Query all logged violations."""
    try:
        violations = get_all_violations()
        return jsonify({
            "status": "success",
            "violations_count": len(violations),
            "violations": violations
        }), 200
    except Exception as e:
        logger.error(f"Failed to query violations: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@main_bp.route('/history/<ip>', methods=['GET'])
def ip_history(ip):
    """Return block history for a specific IP."""
    try:
        history = get_ip_block_history(ip)
        return jsonify({"status": "success", "history": history}), 200
    except Exception as e:
        logger.error(f"Failed to query history for {ip}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@main_bp.route('/')
def index():
    """Render the Web GUI Dashboard."""
    return render_template('dashboard.html')
