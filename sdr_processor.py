import subprocess
import threading
import logging
import re
import os
import signal
import time
import sys
from queue import Empty
from database import save_message, get_alias_info, check_alert_words, get_sdr_instances, get_settings
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

def is_garbage_message(message):
    """Detect garbled/noise POCSAG messages.
    Returns True if the message appears to be garbage/noise.
    """
    if not message or len(message.strip()) == 0:
        return True

    msg = message.strip()
    length = len(msg)

    # Very short messages (1-2 chars) are often noise
    if length <= 2:
        return True

    # Count readable characters (letters, digits, common Swedish, common punctuation/spaces)
    readable = sum(1 for c in msg if c.isalnum() or c in ' .,;:!?-()/@&+=%\n\r\täöåÄÖÅ')
    # Count control characters (ASCII 0-31 except tab/newline/cr)
    control = sum(1 for c in msg if ord(c) < 32 and c not in '\t\n\r')
    # Count special/unusual characters
    special = length - readable - control

    readable_ratio = readable / length if length > 0 else 0
    control_ratio = control / length if length > 0 else 0

    # If more than 20% control characters, it's garbage
    if control_ratio > 0.2:
        return True

    # If less than 50% readable characters, it's garbage
    if readable_ratio < 0.5:
        return True

    # Check for excessive unique character diversity (entropy indicator)
    # Real messages tend to have repeated common characters
    if length > 10:
        unique_ratio = len(set(msg)) / length
        # Very high unique ratio + low readable = noise
        if unique_ratio > 0.85 and readable_ratio < 0.7:
            return True

    return False

def on_new_message(callback):
    new_message_callbacks.append(callback)

def parse_multimon_line(line, charset):
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
                if charset != 'SE':
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

# Supervisor state
active_instances = {} # instance_id -> { 'p1': proc, 'p2': proc, 'config': dict, 'stop_event': Event }
sdr_thread = None
sync_event = threading.Event()

# Duplicate detection cache: (address, message) -> timestamp
recent_messages_cache = {}
cache_lock = threading.Lock()

def monitor_instance(instance_id, p1, p2, stop_event, config):
    """Monitors the output of a single SDR instance (rtl_fm | multimon-ng)."""
    logger.info(f"Monitor thread started for instance {instance_id} ({config['name']})")
    
    # Stderr logging for rtl_fm
    def log_p1_stderr(p_err):
        try:
            for err_line in iter(p_err.readline, b''):
                if stop_event.is_set(): break
                if err_line:
                    decoded_line = err_line.decode('utf-8', errors='replace').strip()
                    if "Frequency correction" in decoded_line or "Using device" in decoded_line:
                        logger.info(f"[{config['name']}] {decoded_line}")
                    else:
                        logger.debug(f"[{config['name']}] rtl_fm: {decoded_line}")
        except Exception:
            pass

    stderr_thread = threading.Thread(target=log_p1_stderr, args=(p1.stderr,), daemon=True)
    stderr_thread.start()

    try:
        while not stop_event.is_set():
            line = p2.stdout.readline()
            if not line:
                if p2.poll() is not None or p1.poll() is not None:
                    logger.warning(f"Processes for instance {instance_id} ({config['name']}) died.")
                    break
                time.sleep(0.1)
                continue
            
            line = line.strip()
            if not line: continue
            
            if "POCSAG" in line and "Alpha:" in line:
                logger.info(f"[{config['name']}] RAW: {line}")
                parsed = parse_multimon_line(line, config.get('multimon_charset', 'SE'))
                
                if parsed:
                    address = parsed['address']
                    message = parsed['message']
                    bitrate = parsed['bitrate']
                    function_code = parsed['function']
                    freq = config.get('frequency', 'Unknown')

                    # GARBAGE FILTER - drop noise messages (if enabled in settings)
                    settings = get_settings()
                    if settings.get('garbage_filter', 'true') == 'true' and is_garbage_message(message):
                        logger.debug(f"[{config['name']}] GARBAGE DROPPED -> Address: {address}, Msg: {message[:60]}...")
                        continue

                    # DUPLICATE DETECTION
                    now = time.time()
                    msg_key = (address, message)
                    is_duplicate = False
                    
                    with cache_lock:
                        if msg_key in recent_messages_cache:
                            last_time = recent_messages_cache[msg_key]
                            if now - last_time < 60:
                                is_duplicate = True
                        recent_messages_cache[msg_key] = now
                        
                        # Prune cache occasionally
                        if len(recent_messages_cache) > 500:
                            cutoff = now - 300 # Keep last 5 mins
                            keys_to_del = [k for k, v in recent_messages_cache.items() if v < cutoff]
                            for k in keys_to_del: del recent_messages_cache[k]

                    alias_info = get_alias_info(address)
                    alias = alias_info['alias'] if alias_info else ''
                    is_hidden = alias_info['is_hidden'] if alias_info else False
                    
                    if is_hidden:
                        logger.info(f"[{config['name']}] DROPPED (Hidden Alias) -> Address: {address}")
                        for cb in list(new_message_callbacks):
                            try: cb({'type': 'ping'})
                            except Exception: pass
                        continue
                        
                    logger.info(f"[{config['name']}] DECODED -> Address: {address}, Alias: {alias}, Msg: {message} {'(DUPLICATE)' if is_duplicate else ''}")
                    
                    alert_match = check_alert_words(message)
                    msg_id, timestamp = save_message(address, message, alias, function_code, bitrate, frequency=freq, is_duplicate=is_duplicate)
                    
                    metadata = {
                        'bitrate': bitrate,
                        'function': function_code,
                        'frequency': freq,
                        'alert_word': alert_match['word'] if alert_match else None,
                        'alert_color': alert_match['color'] if alert_match else None,
                        'sdr_name': config['name'],
                        'is_duplicate': is_duplicate
                    }
                    
                    publish_message(address, message, timestamp, alias, metadata=metadata)
                    
                    msg_data = {
                        'type': 'message', 'id': msg_id, 'timestamp': timestamp,
                        'address': address, 'message': message, 'alias': alias,
                        'is_duplicate': is_duplicate
                    }
                    msg_data.update(metadata)
                    for cb in list(new_message_callbacks):
                        try: cb(msg_data)
                        except Exception as e:
                            logger.error(f"Error in SSE callback: {e}")
                            if cb in new_message_callbacks: new_message_callbacks.remove(cb)
    except Exception as e:
        logger.error(f"Error in monitor thread for {config['name']}: {e}")
    finally:
        logger.info(f"Monitor thread for {config['name']} exiting.")
        # Trigger a sync to restart this instance if it wasn't deliberately stopped
        if not stop_event.is_set():
            sync_event.set()

def start_instance(config):
    """Starts the subprocesses for a single SDR instance."""
    freq = config.get('frequency', '169.8M')
    gain = config.get('gain', 'auto')
    serial = config.get('device_serial', '')
    ppm = config.get('ppm_error', '0')
    sample_rate = config.get('sample_rate', '22050')
    resample_rate = config.get('resample_rate', '22050')
    enable_dc = str(config.get('enable_dc_removal', 'true')).lower() == 'true'
    enable_deemp = str(config.get('enable_deemp', 'true')).lower() == 'true'
    
    rtl_cmd = ['rtl_fm', '-f', freq, '-M', 'fm', '-s', sample_rate, '-r', resample_rate]
    if enable_dc: rtl_cmd.extend(['-E', 'dc'])
    if enable_deemp: rtl_cmd.extend(['-E', 'deemp'])
    if ppm and ppm != '0': rtl_cmd.extend(['-p', ppm])
    if gain != 'auto' and gain.strip() != '': rtl_cmd.extend(['-g', gain])
    if serial: rtl_cmd.extend(['-d', serial])

    verbosity = config.get('multimon_verbosity', '1')
    charset = config.get('multimon_charset', 'SE')
    fmt = config.get('multimon_format', 'auto')
    inp = config.get('multimon_input_type', 'raw')
    
    multimon_cmd = [
        'multimon-ng', '-v', verbosity, '-C', charset, '-f', fmt, '-t', inp,
        '-a', 'POCSAG512', '-a', 'POCSAG1200', '-a', 'POCSAG2400', '-'
    ]

    logger.info(f"Starting {config['name']}: {' '.join(rtl_cmd)} | {' '.join(multimon_cmd)}")
    
    try:
        p1 = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
        p2 = subprocess.Popen(multimon_cmd, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        p1.stdout.close() # Allow p1 to receive SIGPIPE if p2 exits
        return p1, p2
    except Exception as e:
        logger.error(f"Failed to start instance {config['name']}: {e}")
        return None, None

def stop_instance_procs(instance_id):
    """Stops the processes and threads for a specific instance."""
    if instance_id in active_instances:
        inst = active_instances[instance_id]
        logger.info(f"Stopping SDR instance: {inst['config']['name']}")
        inst['stop_event'].set()
        
        # Kill processes
        for p in [inst['p2'], inst['p1']]:
            if p:
                try:
                    if p.poll() is None:
                        p.kill()
                        p.wait(timeout=2)
                except Exception: pass
        
        del active_instances[instance_id]

def run_sdr_process():
    """Supervisor loop that synchronizes active processes with DB config."""
    logger.info("SDR Supervisor started.")
    
    while True:
        try:
            sync_event.clear()
            instances_from_db = get_sdr_instances()
            db_ids = [inst['id'] for inst in instances_from_db]
            
            # 1. Stop instances that are deleted or disabled
            for active_id in list(active_instances.keys()):
                db_entry = next((i for i in instances_from_db if i['id'] == active_id), None)
                if not db_entry or not db_entry.get('enabled'):
                    stop_instance_procs(active_id)
            
            # 2. Start or update instances
            for db_inst in instances_from_db:
                if not db_inst.get('enabled', 1):
                    continue
                
                instance_id = db_inst['id']
                
                # Check if we need to start or restart
                should_start = False
                if instance_id not in active_instances:
                    should_start = True
                else:
                    # Check if config changed
                    if active_instances[instance_id]['config'] != db_inst:
                        logger.info(f"Config change detected for {db_inst['name']}. Restarting...")
                        stop_instance_procs(instance_id)
                        should_start = True
                
                if should_start:
                    p1, p2 = start_instance(db_inst)
                    if p1 and p2:
                        stop_event = threading.Event()
                        monitor_thread = threading.Thread(
                            target=monitor_instance, 
                            args=(instance_id, p1, p2, stop_event, db_inst),
                            daemon=True
                        )
                        active_instances[instance_id] = {
                            'p1': p1, 'p2': p2, 
                            'config': db_inst, 
                            'stop_event': stop_event,
                            'thread': monitor_thread
                        }
                        monitor_thread.start()
                    else:
                        logger.error(f"Failed to start {db_inst['name']}. Retrying next sync.")

        except Exception as e:
            logger.error(f"Error in supervisor loop: {e}")
        
        # Wait for either a sync event (settings saved) or periodic check
        sync_event.wait(timeout=10)

def start_sdr_thread():
    global sdr_thread
    if not sdr_thread or not sdr_thread.is_alive():
        sdr_thread = threading.Thread(target=run_sdr_process, daemon=True)
        sdr_thread.start()

def restart_sdr():
    """Trigger the supervisor to re-sync with the database."""
    logger.info("Sync requested for Multi-SDR supervisor.")
    sync_event.set()
