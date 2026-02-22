import subprocess
import threading
import logging
import re
import os
import signal
import time
import sys
from database import save_message, get_settings, get_alias_info
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

# Callbacks for SSE clients
new_message_callbacks = []

def on_new_message(callback):
    new_message_callbacks.append(callback)

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
                # Remove trailing tags and convert <CR><LF> to actual newlines
                message = message.replace('<CR><LF>', '\n')
                message = message.replace('<CR>', '\n').replace('<LF>', '\n')
                message = message.replace('<NUL>', '').replace('<EOT>', '').strip()
                
                # Apply Swedish character translation
                message_translated = translate_swedish_chars(message)
                return address, message_translated
        except Exception as e:
            logger.error(f"Error parsing line: {line}. Error: {e}")
            return None, None
    return None, None

# Global references to the subprocesses and the worker thread
current_p1 = None
current_p2 = None
sdr_thread = None
restart_event = threading.Event()

def run_sdr_process():
    global current_p1, current_p2
    
    while True:
        restart_event.clear()
        
        # Reload settings from DB
        settings = get_settings()
        freq = settings.get('frequency', '169.8M')
        gain = settings.get('gain', 'auto')
        device_serial = settings.get('device_serial', '')
        
        rtl_cmd = ['rtl_fm', '-f', freq, '-M', 'fm', '-s', '22050', '-E', 'deemp']
        
        if gain != 'auto':
            rtl_cmd.extend(['-g', gain])
            
        if device_serial:
            rtl_cmd.extend(['-d', device_serial])
            logger.info(f"Using RTL-SDR serial: {device_serial}")
        else:
            logger.info("Using default local USB RTL-SDR device")

        multimon_cmd = ['multimon-ng', '-a', 'POCSAG512', '-a', 'POCSAG1200', '-a', 'POCSAG2400', '-f', 'alpha', '-']

        logger.info(f"Starting rtl_fm: {' '.join(rtl_cmd)}")
        logger.info(f"Starting multimon-ng: {' '.join(multimon_cmd)}")

        try:
            current_p1 = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            current_p2 = subprocess.Popen(multimon_cmd, stdin=current_p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            # Read stderr in a separate thread so it doesn't block p1
            def log_p1_stderr(p_err):
                try:
                    for err_line in iter(p_err.readline, ''):
                        if err_line:
                            logger.error(f"rtl_fm stderr: {err_line.strip()}")
                except ValueError:
                    # Occurs when the file is closed on terminated process
                    pass
            
            stderr_thread = threading.Thread(target=log_p1_stderr, args=(current_p1.stderr,), daemon=True)
            stderr_thread.start()

            current_p1.stdout.close() # Allow p1 to receive a SIGPIPE if p2 exits

            # Poll for output or restart requests
            while not restart_event.is_set():
                line = current_p2.stdout.readline()
                if not line:
                    if current_p2.poll() is not None:
                        # Process exited
                        break
                    time.sleep(0.1)
                    continue

                line = line.strip()
                if not line:
                    continue
                
                if "POCSAG" in line and "Alpha:" in line:
                    logger.info(f"RAW: {line}")
                    address, message = parse_multimon_line(line)
                    
                    if address and message:
                        alias_info = get_alias_info(address)
                        alias = alias_info['alias'] if alias_info else ''
                        is_hidden = alias_info['is_hidden'] if alias_info else False
                        
                        if is_hidden:
                            logger.info(f"DROPPED (Hidden Alias) -> Address: {address}, Msg: {message}")
                            continue
                            
                        logger.info(f"DECODED -> Address: {address}, Alias: {alias}, Msg: {message}")
                        
                        timestamp = save_message(address, message, alias)
                        publish_message(address, message, timestamp, alias)
                        
                        msg_data = {
                            'id': timestamp, # use timestamp as temporary ID for SSE
                            'timestamp': timestamp,
                            'address': address,
                            'message': message,
                            'alias': alias
                        }
                        for cb in list(new_message_callbacks):
                            try:
                                cb(msg_data)
                            except Exception as e:
                                logger.error(f"Error in SSE callback: {e}")
                                new_message_callbacks.remove(cb)

            # Cleanup before loop repeats or exits
            cleanup_subprocesses()

            if not restart_event.is_set():
                logger.warning("SDR processes exited unexpectedly. Restarting in 5 seconds...")
                time.sleep(5)

        except Exception as e:
            logger.error(f"SDR process failed: {e}")
            cleanup_subprocesses()
            time.sleep(5) # Delay before attempting restart on crash

def cleanup_subprocesses():
    global current_p1, current_p2
    try:
        if current_p2:
            if current_p2.poll() is None:
                current_p2.kill()
                current_p2.wait(timeout=2)
            if current_p2.stdout:
                current_p2.stdout.close()
    except Exception:
        pass
    try:
        if current_p1:
            if current_p1.poll() is None:
                current_p1.kill()
                current_p1.wait(timeout=2)
            if current_p1.stderr:
                current_p1.stderr.close()
    except Exception:
        pass
        
    current_p1 = None
    current_p2 = None

def start_sdr_thread():
    global sdr_thread
    sdr_thread = threading.Thread(target=run_sdr_process, daemon=True)
    sdr_thread.start()

def restart_sdr():
    """Trigger a restart of the SDR processing thread to apply new settings."""
    logger.info("Restarting SDR processes to apply new settings...")
    restart_event.set()
