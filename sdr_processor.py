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
    # Example format: POCSAG1200: Address: 1234567  Function: 3  Alpha:   THIS IS A TEST MESSAGE<NUL>
    if "POCSAG" in line and "Alpha:" in line:
        try:
            # Extract bitrate/protocol
            bitrate = ""
            if "POCSAG512" in line: bitrate = "512"
            elif "POCSAG1200" in line: bitrate = "1200"
            elif "POCSAG2400" in line: bitrate = "2400"

            # Extract address
            address_match = re.search(r'Address:\s*(\d+)', line)
            if not address_match:
                return None
            address = address_match.group(1)
            
            # Extract function code
            func_match = re.search(r'Function:\s*(\d+)', line)
            function_code = int(func_match.group(1)) if func_match else 0

            # Extract message
            parts = line.split("Alpha:")
            if len(parts) > 1:
                message = parts[1].strip()
                # Remove trailing tags and convert <CR><LF> to actual newlines
                message = message.replace('<CR><LF>', '\n')
                message = message.replace('<CR>', '\n').replace('<LF>', '\n')
                message = message.replace('<NUL>', '').replace('<EOT>', '').strip()
                
                # Apply Swedish character translation IF not using native charset support
                if settings.get('multimon_charset', 'SE') != 'SE':
                    message = translate_swedish_chars(message)
                
                return {
                    'address': address,
                    'message': message,
                    'bitrate': bitrate,
                    'function': function_code
                }
        except Exception as e:
            logger.error(f"Error parsing line: {line}. Error: {e}")
            return None
    return None

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

        verbosity = settings.get('multimon_verbosity', '1')
        charset = settings.get('multimon_charset', 'SE')
        msg_format = settings.get('multimon_format', 'any')
        
        multimon_cmd = [
            'multimon-ng', 
            '-v', verbosity,
            '-C', charset,
            '-f', msg_format,
            '-a', 'POCSAG512', 
            '-a', 'POCSAG1200', 
            '-a', 'POCSAG2400', 
            '-'
        ]

        logger.info(f"Starting rtl_fm: {' '.join(rtl_cmd)}")
        logger.info(f"Starting multimon-ng: {' '.join(multimon_cmd)}")

        try:
            current_p1 = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
            current_p2 = subprocess.Popen(multimon_cmd, stdin=current_p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            # Read stderr in a separate thread so it doesn't block p1
            def log_p1_stderr(p_err):
                try:
                    for err_line in iter(p_err.readline, b''):
                        if err_line:
                            decoded_line = err_line.decode('utf-8', errors='replace').strip()
                            logger.error(f"rtl_fm stderr: {decoded_line}")
                except (ValueError, Exception) as e:
                    # Occurs when the file is closed on terminated process
                    pass
            
            stderr_thread = threading.Thread(target=log_p1_stderr, args=(current_p1.stderr,), daemon=True)
            stderr_thread.start()

            current_p1.stdout.close() # Allow p1 to receive a SIGPIPE if p2 exits

            # Poll for output or restart requests
            while not restart_event.is_set():
                line = ""
                try:
                    line = current_p2.stdout.readline()
                except Exception:
                    # Likely process killed
                    break

                if not line:
                    p2_status = current_p2.poll()
                    p1_status = current_p1.poll()
                    if p2_status is not None or p1_status is not None:
                        logger.warning(f"SDR processes exited. p2 logic: {p2_status}, p1 status: {p1_status}")
                        break
                    time.sleep(0.1)
                    continue

                line = line.strip()
                if not line:
                    continue
                
                if "POCSAG" in line and "Alpha:" in line:
                    logger.info(f"RAW: {line}")
                    parsed = parse_multimon_line(line)
                    
                    if parsed:
                        address = parsed['address']
                        message = parsed['message']
                        bitrate = parsed['bitrate']
                        function_code = parsed['function']

                        alias_info = get_alias_info(address)
                        alias = alias_info['alias'] if alias_info else ''
                        is_hidden = alias_info['is_hidden'] if alias_info else False
                        
                        if is_hidden:
                            logger.info(f"DROPPED (Hidden Alias) -> Address: {address}, Msg: {message}")
                            # Send a ping so the UI knows activity happened
                            for cb in list(new_message_callbacks):
                                try:
                                    cb({'type': 'ping'})
                                except Exception:
                                    pass
                            continue
                            
                        logger.info(f"DECODED -> Bitrate: {bitrate}, Function: {function_code}, Address: {address}, Alias: {alias}, Msg: {message}")
                        
                        timestamp = save_message(address, message, alias, function_code, bitrate)
                        publish_message(address, message, timestamp, alias)
                        
                        msg_data = {
                            'type': 'message',
                            'id': timestamp, # use timestamp as temporary ID for SSE
                            'timestamp': timestamp,
                            'address': address,
                            'message': message,
                            'alias': alias,
                            'bitrate': bitrate,
                            'function': function_code
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
    # Immediately kill processes to force the thread to loop and reload settings
    cleanup_subprocesses()
