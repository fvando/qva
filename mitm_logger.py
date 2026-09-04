"""
mitmproxy addon para logar tráfego HTTP/HTTPS de forma estruturada.
Útil para reverse engineering da app iSwi.
"""
import json
import logging
from datetime import datetime
from mitmproxy import http
from pathlib import Path

# Setup logging
log_file = Path("d:/ott/qva/mitm_traffic.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MitmLogger:
    def request(self, flow: http.HTTPFlow) -> None:
        """Log outgoing requests."""
        try:
            req = flow.request
            # Filtra por host/path de interesse
            if any(x in req.host.lower() for x in ['iswi', 'isiwi', '192.168.1.23', 'camera', 'stream']):
                logger.info(f"REQUEST: {req.method} {req.host}{req.path}")
                logger.info(f"  Headers: {dict(req.headers)}")
                if req.content:
                    try:
                        logger.info(f"  Body: {req.text[:500]}")
                    except:
                        logger.info(f"  Body: [binary, {len(req.content)} bytes]")
        except Exception as e:
            logger.error(f"Error logging request: {e}")

    def response(self, flow: http.HTTPFlow) -> None:
        """Log incoming responses."""
        try:
            resp = flow.response
            req = flow.request
            if any(x in req.host.lower() for x in ['iswi', 'isiwi', '192.168.1.23', 'camera', 'stream']):
                logger.info(f"RESPONSE: {resp.status_code} from {req.host}{req.path}")
                logger.info(f"  Headers: {dict(resp.headers)}")
                if resp.content:
                    try:
                        logger.info(f"  Body: {resp.text[:500]}")
                    except:
                        logger.info(f"  Body: [binary, {len(resp.content)} bytes]")
        except Exception as e:
            logger.error(f"Error logging response: {e}")

addons = [MitmLogger()]
