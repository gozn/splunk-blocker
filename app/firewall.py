import urllib.request
import urllib.parse
import ssl
import logging
from config.settings import PALO_ALTO_URL, PALO_ALTO_VERIFY_SSL

logger = logging.getLogger(__name__)

def call_paloalto_api(cmd):
    """Call Palo Alto user-id API with the specified command XML."""
    if not PALO_ALTO_URL:
        logger.warning("PALO_ALTO_URL is not configured; skipping Palo Alto API call")
        return None

    data = urllib.parse.urlencode({'cmd': cmd}).encode('utf-8')
    
    ctx = ssl.create_default_context()
    if not PALO_ALTO_VERIFY_SSL:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(PALO_ALTO_URL, data=data, method='POST')
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            resp_body = response.read().decode('utf-8')
            logger.info("Palo Alto API response: %s", resp_body)
            return resp_body
    except Exception as e:
        logger.error("Failed to call Palo Alto API: %s", e)
        return None

def block_ip(client_ip, duration_minutes):
    """Register IP block on Palo Alto Firewall."""
    timeout_seconds = duration_minutes * 60
    cmd = f'<uid-message><type>update</type><payload><register><entry ip="{client_ip}"><tag><member timeout="{timeout_seconds}">Splunk_Blocked</member></tag></entry></register></payload></uid-message>'
    return call_paloalto_api(cmd)

def unblock_ip(client_ip):
    """Unregister/remove IP block from Palo Alto Firewall."""
    cmd = f'<uid-message><type>update</type><payload><unregister><entry ip="{client_ip}"><tag><member>Splunk_Blocked</member></tag></entry></unregister></payload></uid-message>'
    return call_paloalto_api(cmd)
