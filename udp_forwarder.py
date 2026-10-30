"""
udp_forwarder.py - UDP JSON forwarder for PagerMonitor
Forwards decoded POCSAG messages as full JSON datagrams to one or more remote host:port targets.
Configuration is strictly managed via environment variables:
  UDP_FORWARD_HOST     - Target IP(s) or hostname(s), comma-separated (e.g. 192.168.1.100,192.168.1.101 or 192.168.1.100:5599,192.168.1.101:6000)
  UDP_FORWARD_PORT     - Target UDP port(s), single default port or comma-separated (e.g. 5599)
  UDP_FORWARD_ENABLED  - 'true' or 'false' (defaults to true if at least one valid host:port target is configured)
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
_targets = []  # List of (host, port) tuples
_packets_sent = 0
_last_sent_time = None


def _parse_targets(host_raw: str, port_raw: str) -> list:
    """
    Parses UDP_FORWARD_HOST and UDP_FORWARD_PORT into a list of (host, port) tuples.
    Supports:
      - Single host and port: UDP_FORWARD_HOST=192.168.1.100, UDP_FORWARD_PORT=5599
      - Comma-separated hosts sharing one port: UDP_FORWARD_HOST=192.168.1.100,192.168.1.101, UDP_FORWARD_PORT=5599
      - Inline host:port per entry: UDP_FORWARD_HOST=192.168.1.100:5599,192.168.1.101:6000
      - Comma-separated hosts and matching comma-separated ports
    """
    if not host_raw:
        return []

    raw_hosts = [h.strip() for h in host_raw.split(',') if h.strip()]
    if not raw_hosts:
        return []

    raw_ports = [p.strip() for p in port_raw.split(',') if p.strip()] if port_raw else []
    parsed_ports = []
    for p_str in raw_ports:
        try:
            p_val = int(p_str)
            if 1 <= p_val <= 65535:
                parsed_ports.append(p_val)
            else:
                logger.error(f"[UDP] Out-of-range UDP_FORWARD_PORT value: '{p_str}'")
                parsed_ports.append(0)
        except ValueError:
            logger.error(f"[UDP] Invalid UDP_FORWARD_PORT value: '{p_str}'")
            parsed_ports.append(0)

    default_port = parsed_ports[0] if len(parsed_ports) == 1 else 0

    targets = []
    for idx, entry in enumerate(raw_hosts):
        h = entry
        p = 0
        if ':' in entry:
            host_part, port_part = entry.rsplit(':', 1)
            h = host_part.strip()
            try:
                p_val = int(port_part.strip())
                if 1 <= p_val <= 65535:
                    p = p_val
                else:
                    logger.error(f"[UDP] Out-of-range inline port in UDP_FORWARD_HOST entry: '{entry}'")
            except ValueError:
                logger.error(f"[UDP] Invalid inline port in UDP_FORWARD_HOST entry: '{entry}'")
        else:
            if len(parsed_ports) > 1 and idx < len(parsed_ports):
                p = parsed_ports[idx]
            elif default_port > 0:
                p = default_port
            elif len(parsed_ports) > 0:
                p = parsed_ports[0]

        if h and p > 0:
            target_tuple = (h, p)
            if target_tuple not in targets:
                targets.append(target_tuple)

    return targets


def init_udp_forwarder():
    """
    Initializes UDP forwarder configuration from environment variables.
    Can be safely called multiple times (e.g. in tests or at startup).
    """
    global _sock, _enabled, _target_host, _target_port, _targets, _packets_sent, _last_sent_time
    with _lock:
        host_raw = os.environ.get('UDP_FORWARD_HOST', '').strip()
        port_raw = os.environ.get('UDP_FORWARD_PORT', '').strip()
        enabled_raw = os.environ.get('UDP_FORWARD_ENABLED', '').strip().lower()

        targets = _parse_targets(host_raw, port_raw)

        if enabled_raw in ('true', '1', 'yes'):
            enabled = True
        elif enabled_raw in ('false', '0', 'no'):
            enabled = False
        else:
            # If not explicitly specified, enable automatically if at least one valid target is configured
            enabled = len(targets) > 0

        _targets = targets
        if targets:
            _target_host = ",".join(h for h, _ in targets)
            _target_port = targets[0][1]
        else:
            _target_host = host_raw
            _target_port = 0

        _enabled = enabled and len(_targets) > 0

        if _sock:
            try:
                _sock.close()
            except Exception:
                pass
            _sock = None

        if _enabled:
            try:
                _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                targets_str = ", ".join(f"{h}:{p}" for h, p in _targets)
                logger.info(f"[UDP] POCSAG JSON forwarder active -> {targets_str}")
            except Exception as e:
                logger.error(f"[UDP] Failed to create UDP socket: {e}")
                _enabled = False
        else:
            if host_raw or port_raw:
                logger.info(f"[UDP] POCSAG JSON forwarder is disabled (host={host_raw or 'none'}, port={port_raw or 'none'}, enabled={enabled_raw or 'auto'}).")
            else:
                logger.debug("[UDP] POCSAG JSON forwarder not configured.")

    return _enabled


def is_enabled() -> bool:
    """Returns True if the UDP forwarder is active and configured."""
    return _enabled and len(_targets) > 0


def get_status() -> dict:
    """Returns current runtime status of the UDP forwarder."""
    with _lock:
        return {
            'enabled': _enabled,
            'host': _target_host if _enabled else '',
            'port': _target_port if _enabled else 0,
            'targets': [{'host': h, 'port': p} for h, p in _targets] if _enabled else [],
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
    Forwards a decoded POCSAG message as full JSON over UDP to all configured targets.
    Only POCSAG messages are sent; other protocols are silently ignored.
    
    Returns True if successfully sent to at least one target, False otherwise.
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

        any_sent = False
        for target_host, target_port in _targets:
            try:
                _sock.sendto(data_bytes, (target_host, target_port))
                _packets_sent += 1
                _last_sent_time = datetime.now().isoformat()
                any_sent = True
                logger.debug(f"[UDP] Forwarded POCSAG JSON packet #{_packets_sent} to {target_host}:{target_port} ({len(data_bytes)} bytes)")
            except Exception as e:
                logger.warning(f"[UDP] Error sending UDP packet to {target_host}:{target_port}: {e}")

        return any_sent


# Auto-initialize on module import
init_udp_forwarder()
