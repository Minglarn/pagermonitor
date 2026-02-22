import subprocess
import threading
import logging
import re
import os
import signal
import sys
from database import save_message
from mqtt_client import publish_message

logger = logging.getLogger(__name__)

# Översättningstabell för svenska tecken
CHAR_MAP = {
    '[': 'Ä',
    '\\': 'Ö',
    ']': 'Å',
    '{': 'ä',
    '|': 'ö',
    '}': 'å'
}

def translate_swedish_chars(text):
    for k, v in CHAR_MAP.items():
        text = text.replace(k, v)
    return text

def parse_multimon_line(line):
    # Example format: POCSAG512: Address: 1234567  Function: 3  Alpha:   THIS IS A TEST MESSAGE<NUL>
    # or Alphanumeric message parsing
    if "POCSAG" in line and "Alpha:" in line:
        try:
            # Extract address
            address_match = re.search(r'Address:\s*(\d+)', line)
            if not address_match:
                return None, None
            address = address_match.group(1)
            
            # Extract message
            parts = line.split("Alpha:")
            if len(parts) > 1:
                message = parts[1].strip()
                # Remove trailing <NUL> and other tags if any
                message = message.replace('<NUL>', '').replace('<EOT>', '').strip()
                
                # Apply Swedish character translation
                message_translated = translate_swedish_chars(message)
                return address, message_translated
        except Exception as e:
            logger.error(f"Error parsing line: {line}. Error: {e}")
            return None, None
    return None, None

def run_sdr_process():
    rtl_tcp_addr = os.environ.get('RTL_TCP_ADDRESS')
    
    rtl_cmd = ['rtl_fm', '-f', '169.8M', '-M', 'fm', '-s', '22050', '-E', 'deemp']
    if rtl_tcp_addr:
        # Check if user passed full "rtl_tcp:1.2.3.4" or just "1.2.3.4"
        device_arg = rtl_tcp_addr if rtl_tcp_addr.startswith('rtl_tcp:') else f'rtl_tcp:{rtl_tcp_addr}'
        rtl_cmd.extend(['-d', device_arg])
        logger.info(f"Using RTL_TCP device: {device_arg}")
    else:
        logger.info("Using local USB RTL-SDR device")

    multimon_cmd = ['multimon-ng', '-a', 'POCSAG512', '-a', 'POCSAG1200', '-a', 'POCSAG2400', '-f', 'alpha', '-']

    logger.info(f"Starting rtl_fm: {' '.join(rtl_cmd)}")
    logger.info(f"Starting multimon-ng: {' '.join(multimon_cmd)}")

    try:
        p1 = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(multimon_cmd, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        p1.stdout.close() # Allow p1 to receive a SIGPIPE if p2 exits

        for line in iter(p2.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
            
            # Only log actual decode lines to avoid spam
            if "POCSAG" in line:
                logger.info(f"RAW: {line}")
                address, message = parse_multimon_line(line)
                
                if address and message:
                    logger.info(f"DECODED -> Address: {address}, Msg: {message}")
                    timestamp = save_message(address, message)
                    publish_message(address, message, timestamp)

        p2.stdout.close()
        p2.wait()
        p1.wait()

    except Exception as e:
        logger.error(f"SDR process failed: {e}")

def start_sdr_thread():
    thread = threading.Thread(target=run_sdr_process, daemon=True)
    thread.start()
    return thread
