// Update UTC Clock
function updateClock() {
    const clockEl = document.getElementById('clock');
    if (!clockEl) return;
    const now = new Date();
    const utcString = now.toUTCString().replace('GMT', 'UTC');
    clockEl.textContent = utcString.split(' ').slice(4).join(' ') + ' UTC';
}
setInterval(updateClock, 1000);
updateClock();

// Fluctuating Dashboard Metrics (Simulation to make it feel alive)
function fluctuateMetrics() {
    const connEl = document.getElementById('conn-count');
    const fwEl = document.getElementById('fw-rate');
    
    if (connEl) {
        const currentConn = parseInt(connEl.textContent, 10) || 142;
        const change = Math.floor(Math.random() * 7) - 3; // -3 to +3
        connEl.textContent = Math.max(80, Math.min(300, currentConn + change));
    }
    
    if (fwEl) {
        const baseRate = 99.95;
        const randomAddition = Math.random() * 0.04;
        fwEl.textContent = (baseRate + randomAddition).toFixed(2) + '%';
    }

    // Add background system logs occasionally
    if (Math.random() < 0.25) {
        const messages = [
            "[INFO] performing routine firewall rule audit...",
            "[INFO] SSL certificates validated successfully.",
            "[INFO] IP reputation database updated.",
            "[INFO] zero-day threat database synchronized.",
            "[INFO] backup snapshot verified on NODE-01."
        ];
        const randomMsg = messages[Math.floor(Math.random() * messages.length)];
        logToConsole(randomMsg, 'system-msg');
    }
}
setInterval(fluctuateMetrics, 4000);

// Helper function to log lines to the Mock Console
function logToConsole(message, typeClass = 'system-msg') {
    const consoleOutput = document.getElementById('console-output');
    if (!consoleOutput) return;
    
    const line = document.createElement('div');
    line.className = `console-line ${typeClass}`;
    line.textContent = message;
    consoleOutput.appendChild(line);
    
    // Auto scroll to bottom
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// Trigger Log Action
// Sends a real network request that will generate access-log entries on Nginx
async function triggerLogAction(actionType) {
    const feedbackText = document.getElementById('api-response-text');
    const feedbackBox = document.getElementById('api-feedback-box');
    
    if (!feedbackText) return;
    
    // Disable action buttons temporarily
    const buttons = document.querySelectorAll('.cyber-btn');
    buttons.forEach(btn => btn.disabled = true);
    
    let endpoint = '';
    let method = 'GET';
    let payload = null;
    
    switch(actionType) {
        case 'audit':
            endpoint = `/api/audit?timestamp=${Date.now()}`;
            logToConsole(`[ACTION] User triggered Manual System Audit`, 'system-msg');
            break;
        case 'diagnostics':
            endpoint = `/api/diagnostics?node=01&verbose=true`;
            logToConsole(`[ACTION] Initiating live network diagnostic scan`, 'system-msg');
            break;
        case 'simulate-intrusion':
            endpoint = `/api/simulate-intrusion?target=honeypot&protocol=ssh`;
            method = 'POST';
            payload = JSON.stringify({ trigger: "manual_anomaly", severity: "medium" });
            logToConsole(`[WARNING] Simulating anomalous login attempts on ssh honeypot`, 'warning-msg');
            
            // Temporarily set threat level to ELEVATED
            const threatEl = document.getElementById('threat-level');
            if (threatEl) {
                threatEl.textContent = 'ELEVATED';
                threatEl.className = 'metric-value text-orange';
                setTimeout(() => {
                    threatEl.textContent = 'STABLE';
                    threatEl.className = 'metric-value text-green';
                }, 15000);
            }
            break;
        case 'critical-alert':
            endpoint = `/api/critical-alert/raise`;
            method = 'POST';
            payload = JSON.stringify({ alert: "critical_syslog_test" });
            logToConsole(`[CRITICAL] ALARM TRIGGERED: testing syslog/HEC forwarding path`, 'error-msg');
            
            // Flash status
            const pulse = document.getElementById('header-pulse');
            if (pulse) {
                pulse.className = 'pulse-indicator status-red';
                setTimeout(() => {
                    pulse.className = 'pulse-indicator status-green';
                }, 5000);
            }
            break;
    }
    
    feedbackText.textContent = `Sending ${method} request to ${endpoint}...`;
    logToConsole(`[HTTP] ${method} ${endpoint} (fetching...)`, 'system-msg');
    
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'SOC-Portal-Client',
                'X-SOC-Event': actionType
            }
        };
        if (payload) options.body = payload;
        
        const response = await fetch(endpoint, options);
        
        // Even if Nginx returns 404 (because these are mock routes), we successfully generated an access log entry!
        const statusText = `${response.status} ${response.statusText || 'OK'}`;
        feedbackText.textContent = `Status: ${statusText} | Request Logged to Nginx`;
        
        const isSuccess = response.ok;
        const msgClass = isSuccess ? 'success-msg' : (response.status >= 500 ? 'error-msg' : 'warning-msg');
        logToConsole(`[RESPONSE] ${method} ${endpoint} -> Status ${statusText} (Logged to Splunk)`, msgClass);
        
    } catch (error) {
        // Direct network error (e.g. host unreachable)
        feedbackText.textContent = `Error: ${error.message}`;
        logToConsole(`[ERROR] Connection failed: ${error.message}`, 'error-msg');
    } finally {
        // Re-enable buttons
        buttons.forEach(btn => btn.disabled = false);
    }
}
