"""
udp_forwarder.py - UDP JSON forwarder for PagerMonitor
Forwards decoded POCSAG messages as full JSON datagrams to a remote host:port.
Configuration is strictly managed via environment variables:
  UDP_FORWARD_HOST     - Target IP or hostname (e.g. 192.168.1.100)
  UDP_FORWARD_PORT     - Target UDP port (e.g. 5599)
  UDP_FORWARD_ENABLED  - 'true' or 'false' (defaults to true if host and port are configured)
"""

import os
import json
import socket
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_sock = None
_enabled = False
_target_host = ""
_target_port = 0
_packets_sent = 0
_last_sent_time = None


def init_udp_forwarder():
    """
    Initializes UDP forwarder configuration from environment variables.
    Can be safely called multiple times (e.g. in tests or at startup).
    """
    global _sock, _enabled, _target_host, _target_port, _packets_sent, _last_sent_time
    with _lock:
        host = os.environ.get('UDP_FORWARD_HOST', '').strip()
        port_raw = os.environ.get('UDP_FORWARD_PORT', '').strip()
        enabled_raw = os.environ.get('UDP_FORWARD_ENABLED', '').strip().lower()

        port = 0
        if port_raw:
            try:
                port = int(port_raw)
            except ValueError:
                logger.error(f"[UDP] Invalid UDP_FORWARD_PORT value: '{port_raw}'")
                port = 0

        if enabled_raw in ('true', '1', 'yes'):
            enabled = True
        elif enabled_raw in ('false', '0', 'no'):
            enabled = False
        else:
            # If not explicitly specified, enable automatically if both host and valid port are set
            enabled = bool(host and port > 0)

        _target_host = host
        _target_port = port
        _enabled = enabled and bool(host) and (port > 0)

        if _sock:
            try:
                _sock.close()
            except Exception:
                pass
            _sock = None

        if _enabled:
            try:
                _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                logger.info(f"[UDP] POCSAG JSON forwarder active -> {_target_host}:{_target_port}")
            except Exception as e:
                logger.error(f"[UDP] Failed to create UDP socket: {e}")
                _enabled = False
        else:
            if host or port > 0:
                logger.info(f"[UDP] POCSAG JSON forwarder is disabled (host={host or 'none'}, port={port or 'none'}, enabled={enabled_raw or 'auto'}).")
            else:
                logger.debug("[UDP] POCSAG JSON forwarder not configured.")

    return _enabled


def is_enabled() -> bool:
    """Returns True if the UDP forwarder is active and configured."""
    return _enabled and bool(_target_host) and (_target_port > 0)


def get_status() -> dict:
    """Returns current runtime status of the UDP forwarder."""
    with _lock:
        return {
            'enabled': _enabled,
            'host': _target_host,
            'port': _target_port,
            'packets_sent': _packets_sent,
            'last_sent_time': _last_sent_time
        }


def _sanitize_for_json(obj):
    """Recursively converts non-serializable objects (datetime, sets) into standard JSON types."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(i) for i in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (bytes, bytearray)):
        return obj.decode('utf-8', errors='replace')
    return obj


def forward_pocsag(payload: dict) -> bool:
    """
    Forwards a decoded POCSAG message as full JSON over UDP.
    Only POCSAG messages are sent; other protocols are silently ignored.
    
    Returns True if successfully sent, False otherwise.
    """
    global _sock, _packets_sent, _last_sent_time

    if not payload or not isinstance(payload, dict):
        return False

    if not is_enabled():
        return False

    # Strictly filter for POCSAG protocol
    protocol = str(payload.get('protocol') or '').strip().upper()
    bitrate = str(payload.get('bitrate') or '').strip().upper()
    if 'POCSAG' not in protocol and 'POCSAG' not in bitrate:
        return False

    # Construct the full JSON payload
    try:
        sanitized = _sanitize_for_json(payload)
        json_data = json.dumps(sanitized, ensure_ascii=False)
        data_bytes = json_data.encode('utf-8')
    except Exception as e:
        logger.error(f"[UDP] Failed to serialize POCSAG message to JSON: {e}")
        return False

    with _lock:
        if not _sock:
            try:
                _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            except Exception as e:
                logger.error(f"[UDP] Failed to re-create UDP socket: {e}")
                return False

        try:
            _sock.sendto(data_bytes, (_target_host, _target_port))
            _packets_sent += 1
            _last_sent_time = datetime.now().isoformat()
            logger.debug(f"[UDP] Forwarded POCSAG JSON packet #{_packets_sent} to {_target_host}:{_target_port} ({len(data_bytes)} bytes)")
            return True
        except Exception as e:
            logger.warning(f"[UDP] Error sending UDP packet to {_target_host}:{_target_port}: {e}")
            return False


# Auto-initialize on module import
init_udp_forwarder()
