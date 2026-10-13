import subprocess
import threading
import logging
import re
import os
import signal
import time
import sys
from datetime import datetime
from queue import Empty
from database import save_message, get_alias_info, check_alert_words, get_sdr_instances, get_settings, increment_message_repeat
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

def is_garbage_message(message, sensitivity=50):
    """Detect garbled/noise POCSAG messages using enhanced heuristics.
    Returns True if the message appears to be garbage/noise.
    sensitivity: 0 (lenient) to 100 (strict).
    """
    if not message or len(message.strip()) == 0:
        return True

    msg = message.strip()
    
    # multimon-ng outputs control chars as <TAG> (e.g. <SOH>, <DC1>, <EOT>)
    # We replace them with a single unprintable control char (\x01) for accurate analysis.
    temp_msg = re.sub(r'<[A-Z0-9]{2,4}>', '\x01', msg)
    length = len(temp_msg)

    if length == 0:
        return True

    # Short alphanumeric messages (like 'AB', 'CD', 'P1', 'OK') are valid pager status codes
    if length < 3:
        if temp_msg.isalnum():
            return False
        return True

    # Scale thresholds based on sensitivity (0-100)
    # readable_ratio_min: 0.50 (lenient) -> 0.80 (strict)
    readable_min = 0.50 + (sensitivity / 100.0) * 0.30
    # control_ratio_max: 0.25 (lenient) -> 0.05 (strict)
    control_max = 0.25 - (sensitivity / 100.0) * 0.20

    # Count readable characters (letters, digits, common Swedish, punctuation, separators, symbols)
    readable = sum(1 for c in temp_msg if c.isalnum() or c in ' .,;:!?-()/@&+=%*#_"\n\r\täöåÄÖÅ')
    # Count control characters (ASCII 0-31 except tab/newline/cr)
    control = sum(1 for c in temp_msg if ord(c) < 32 and c not in '\t\n\r')

    readable_ratio = readable / length
    control_ratio = control / length

    # Too many control characters
    if control_ratio > control_max:
        return True

    # Pattern check: Too many consecutive noise symbols.
    # Standard formatting characters (such as hyphens '-', equal signs '=', dots '...', asterisks '***', underscores '___')
    # are frequently used in pager dispatches as section headers or end-of-message footers.
    # Therefore, we only reject clusters of non-formatting noise symbols, and skip this check if the message is highly readable.
    if readable_ratio < 0.85:
        # Check for sequences of obscure noise symbols
        if re.search(r'[~|\\^{}\$@\x00-\x1f]{3,}', temp_msg):
            return True
        if re.search(r'[^a-zA-Z0-9\såäöÅÄÖ\-=\._\*/:;!\?,()\"\'%#]{3,}', temp_msg):
            return True

    # Entropy check for longer messages
    if length > 5:
        unique_ratio = len(set(temp_msg)) / length
        # High entropy but low readable ratio often indicates random noise
        if unique_ratio > 0.70 and readable_ratio < 0.90:
            return True
        # Repetitive noise check: messages repeating only 1-3 distinct characters (e.g. "=====", "AAAAAA", "121212")
        if length > 15 and len(set(temp_msg)) <= 3:
            return True

    # Linguistic Heuristics:
    vowels = len(re.findall(r'[aeiouyåäöAEIOUYÅÄÖ]', temp_msg))
    digits = len(re.findall(r'\d', temp_msg))
    letters = re.findall(r'[a-zA-ZåäöÅÄÖ]', temp_msg)
    
    # Check for random case toggling: "F'sCUi"
    if len(letters) > 4:
        case_changes = 0
        for i in range(1, len(temp_msg)):
            if temp_msg[i].isalpha() and temp_msg[i-1].isalpha():
                if temp_msg[i].isupper() != temp_msg[i-1].isupper():
                    case_changes += 1
        if (case_changes / len(letters)) > 0.35 and readable_ratio < 0.90:
            return True

    # Real messages usually have some vowels if they contain letters and no digits
    if len(letters) >= 3 and vowels == 0 and digits < 2:
        return True

    # Too few readable characters
    if readable_ratio < readable_min:
        return True

    return False

def on_new_message(callback):
    new_message_callbacks.append(callback)

def parse_multimon_line(line, charset):
    """Parses a single line from multimon-ng output."""
    try:
        protocol_type = "POCSAG"
        # Look for AFSK or UFSK followed by a colon
        if re.search(r'(AFSK|UFSK)\d*:', line):
            protocol_type = "AFSK"

        if protocol_type == "POCSAG":
            if "Alpha:" not in line:
                return None
            
            # Extract bitrate
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
            message = parts[1].strip()
        else:
            # AFSK/UFSK/etc formatting: "AFSK1200: fm CALLSIGN-1 to DEST ..."
            # Split by the first colon to get protocol name and content
            proto_part, content = line.split(":", 1)
            content = content.strip()
            
            address = "AFSK"
            # Extract bitrate or mode part
            bitrate = re.sub(r'^(AFSK|UFSK)', '', proto_part).strip() or "1200"
            function_code = 0
            
            # Try to extract the source callsign as the address
            source_match = re.search(r'fm\s+([\w-]+)', content)
            if source_match:
                address = source_match.group(1)
            
            message = content
            protocol_type = proto_part.strip()

        # POST-PROCESSING (Shared)
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
            'protocol': protocol_type,
            'function': function_code
        }
    except Exception as e:
        logger.error(f"Error parsing line: {line}. Error: {e}")
        return None

# Supervisor state
active_instances = {} # instance_id -> { 'p1': proc, 'p2': proc, 'config': dict, 'stop_event': Event, 'started_at': float }
instance_errors = {}  # instance_id -> list of recent error messages
sdr_thread = None
sync_event = threading.Event()

# Duplicate detection cache: (address, message) -> timestamp
recent_messages_cache = {}
cache_lock = threading.Lock()

def monitor_instance(instance_id, p1, p2, stop_event, config):
    """Monitors the output of a single SDR instance (rtl_fm | multimon-ng)."""
    logger.info(f"Monitor thread started for instance {instance_id} ({config['name']})")
    
    # Stderr logging for rtl_fm - log all messages from rtl_fm so startup and errors are visible
    def log_p1_stderr(p_err):
        try:
            for err_line in iter(p_err.readline, b''):
                if stop_event.is_set(): break
                if err_line:
                    decoded_line = err_line.decode('utf-8', errors='replace').strip()
                    if not decoded_line: continue
                    lower_line = decoded_line.lower()
                    
                    is_err = any(w in lower_line for w in [
                        'error', 'failed', 'cannot', 'usb_claim', 'usb_open', 
                        'resetting', 'lost', 'fault', 'critical', 'no matching', 
                        'not found', 'denied', 'busy'
                    ])
                    if is_err:
                        logger.warning(f"[{config['name']}] rtl_fm: {decoded_line}")
                        if instance_id not in instance_errors:
                            instance_errors[instance_id] = []
                        instance_errors[instance_id].append(decoded_line)
                        if len(instance_errors[instance_id]) > 10:
                            instance_errors[instance_id].pop(0)
                    else:
                        logger.info(f"[{config['name']}] rtl_fm: {decoded_line}")
        except Exception as e:
            logger.debug(f"[{config['name']}] rtl_fm stderr reader exception: {e}")

    if p1 and p1.stderr:
        stderr_thread = threading.Thread(target=log_p1_stderr, args=(p1.stderr,), daemon=True)
        stderr_thread.start()

    try:
        while not stop_event.is_set():
            line = p2.stdout.readline()
            if not line:
                if p2.poll() is not None or (p1 and p1.poll() is not None):
                    p1_exit = p1.poll() if p1 else 'N/A'
                    p2_exit = p2.poll() if p2 else 'N/A'
                    last_errs = instance_errors.get(instance_id, [])
                    err_txt = f" (Sista fel fran rtl: '{last_errs[-1]}')" if last_errs else ""
                    logger.warning(
                        f"[{config['name']}] Processer avslutades ovantat! "
                        f"rtl PID={p1.pid if p1 else 'N/A'} exit={p1_exit}, "
                        f"decoder PID={p2.pid if p2 else 'N/A'} exit={p2_exit}.{err_txt}"
                    )
                    break
                time.sleep(0.1)
                continue
            
            line = line.strip()
            if not line: continue
            
            # BROAD LOGGING FOR DEBUGGING - log all output if verbosity is high
            if int(config.get('multimon_verbosity', '1')) >= 2:
                logger.debug(f"[{config['name']}] RAW_ALL: {line}")

            is_pocsag_or_afsk = ("POCSAG" in line and "Alpha:" in line) or re.search(r'(AFSK|UFSK)\d*:', line)
            is_tetra = line.startswith("TETRA:")

            if is_pocsag_or_afsk or is_tetra:
                # Record activity time for watchdog telemetry
                if instance_id in active_instances:
                    active_instances[instance_id]['last_message_time'] = time.time()

                if is_tetra:
                    parts = line.split(" ", 2)
                    tetra_type = parts[1] if len(parts) > 1 else "DATA"
                    rest = parts[2] if len(parts) > 2 else ""

                    if tetra_type == "SCAN":
                        logger.info(f"[{config['name']}] TETRA SCAN: {rest}")
                        continue

                    if tetra_type == "LOCK":
                        freq_match = re.search(r'Freq:\s*([0-9\.]+[kKMm]?)', rest)
                        if freq_match:
                            locked_f = freq_match.group(1)
                            config['active_frequency'] = locked_f
                            logger.info(f"[{config['name']}] TETRA LOCK: Basstation låst på frekvens {locked_f} ({rest})")
                        else:
                            logger.info(f"[{config['name']}] TETRA LOCK: {rest}")
                        continue

                    if tetra_type == "NET":
                        freq_match = re.search(r'(?:Freq:\s*|på\s+)([0-9\.]+[kKMm]?)', rest)
                        if freq_match:
                            config['active_frequency'] = freq_match.group(1)
                        logger.info(f"[{config['name']}] TETRA BASSTATION SYNKRISERAD: {rest}")

                    gssi_match = re.search(r'GSSI:\s*(\d+)', rest)
                    issi_match = re.search(r'ISSI:\s*(\d+)', rest)
                    mcc_match = re.search(r'MCC:\s*(\d+)', rest)
                    mnc_match = re.search(r'MNC:\s*(\d+)', rest)
                    cell_match = re.search(r'Cell:\s*([^\s]+)', rest)
                    msg_match = re.search(r'Msg:\s*(.+)$', rest)

                    if gssi_match:
                        address = gssi_match.group(1)
                    elif issi_match:
                        address = issi_match.group(1)
                    elif tetra_type == "NET":
                        mcc_val = mcc_match.group(1) if mcc_match else "240"
                        mnc_val = mnc_match.group(1) if mnc_match else "01"
                        net_prefix = "RAKEL" if (mcc_val == "240" and mnc_val in ("01", "1")) else "TETRA"
                        if cell_match:
                            address = f"{net_prefix}-C{cell_match.group(1)}"
                        else:
                            address = f"{net_prefix}-{mcc_val}-{mnc_val}"
                    else:
                        address = "TETRA"

                    message_text = msg_match.group(1).strip() if msg_match else rest
                    if tetra_type == "NET":
                        mcc_val = mcc_match.group(1) if mcc_match else "240"
                        mnc_val = mnc_match.group(1) if mnc_match else "01"
                        net_label = "Sverige / Rakel (MSB)" if (mcc_val == "240" and mnc_val in ("01", "1")) else f"MCC: {mcc_val}, MNC: {mnc_val}"
                        if "MCC" not in message_text and "Nät:" not in message_text:
                            message = f"{message_text} | Nät: {net_label}"
                        else:
                            message = message_text
                    else:
                        message = message_text

                    if tetra_type == "SDS":
                        bitrate = "TETRA-SDS"
                        function_code = 3
                        protocol_type = "TETRA"
                    elif tetra_type == "CALL":
                        bitrate = "TETRA-CALL"
                        function_code = 1
                        protocol_type = "TETRA"
                    elif tetra_type == "STATUS":
                        bitrate = "TETRA-STAT"
                        function_code = 2
                        protocol_type = "TETRA"
                    elif tetra_type == "NET":
                        bitrate = "TETRA-NET"
                        function_code = 0
                        protocol_type = "TETRA"
                    else:
                        bitrate = f"TETRA-{tetra_type}"
                        function_code = 0
                        protocol_type = "TETRA"

                    parsed = {
                        'address': address,
                        'message': message,
                        'bitrate': bitrate,
                        'protocol': protocol_type,
                        'function': function_code
                    }
                else:
                    parsed = parse_multimon_line(line, config.get('multimon_charset', 'SE'))
                
                if parsed:
                    address = parsed['address']
                    message = parsed['message']
                    bitrate = parsed['bitrate']
                    protocol_type = parsed['protocol']
                    function_code = parsed['function']
                    freq = config.get('active_frequency', config.get('frequency', 'Unknown'))

                    # ALIAS LOOKUP & MUTING CHECK
                    alias_info = get_alias_info(address)
                    alias = alias_info['alias'] if alias_info else ''
                    is_hidden = alias_info['is_hidden'] if alias_info else False
                    
                    if not alias and is_tetra:
                        if address.startswith("RAKEL"):
                            alias = "Rakel Basstation" if tetra_type == "NET" else "Rakel"
                        elif address.startswith("TETRA"):
                            alias = "TETRA Basstation" if tetra_type == "NET" else "TETRA"
                    
                    if is_hidden:
                        logger.info(f"[{config['name']}] RAW: {line} [DROPPED] Cause: MUTED")
                        for cb in list(new_message_callbacks):
                            try: cb({'type': 'ping'})
                            except Exception: pass
                        continue

                    # GARBAGE FILTER - only filter un-aliased messages (configured aliases are never dropped)
                    has_active_alias = bool(alias_info and not is_hidden)
                    if not has_active_alias:
                        settings = get_settings()
                        if settings.get('garbage_filter', 'true') == 'true':
                            sensitivity = int(settings.get('garbage_filter_sensitivity', '50'))
                            if is_garbage_message(message, sensitivity):
                                logger.info(f"[{config['name']}] RAW: {line} [DROPPED] Cause: GARBAGE")
                                for cb in list(new_message_callbacks):
                                    try: cb({'type': 'ping'})
                                    except Exception: pass
                                continue

                    logger.info(f"[{config['name']}] RAW: {line}")

                    # DUPLICATE DETECTION
                    settings = get_settings()
                    try:
                        dup_window = int(settings.get('duplicate_window', '120'))
                    except (ValueError, TypeError):
                        dup_window = 120
                    dup_handling = settings.get('duplicate_handling', 'merge')

                    now = time.time()
                    msg_key = (address, message)
                    is_duplicate = False
                    cached_entry = None
                    
                    with cache_lock:
                        if msg_key in recent_messages_cache:
                            entry = recent_messages_cache[msg_key]
                            last_time = entry['time'] if isinstance(entry, dict) else entry
                            if (now - last_time) <= dup_window:
                                is_duplicate = True
                                cached_entry = entry if isinstance(entry, dict) else {'time': last_time, 'id': None, 'repeat_count': 1}
                        
                        # Prune cache occasionally
                        if len(recent_messages_cache) > 500:
                            cutoff = now - max(300, dup_window * 2)
                            keys_to_del = [k for k, v in recent_messages_cache.items() if (v['time'] if isinstance(v, dict) else v) < cutoff]
                            for k in keys_to_del: del recent_messages_cache[k]

                    if is_duplicate and dup_handling == 'merge' and cached_entry and cached_entry.get('id'):
                        cached_id = cached_entry['id']
                        now_iso = datetime.now().isoformat()
                        new_count = increment_message_repeat(cached_id, now_iso)
                        cached_entry['time'] = now
                        cached_entry['repeat_count'] = new_count
                        
                        logger.info(f"[{config['name']}] RAW: {line} [MERGED] Repeat count {new_count}x on ID {cached_id}")
                        
                        repeat_data = {
                            'type': 'repeat_update',
                            'id': cached_id,
                            'repeat_count': new_count,
                            'last_timestamp': now_iso,
                            'frequency': freq,
                            'address': address
                        }
                        for cb in list(new_message_callbacks):
                            try: cb(repeat_data)
                            except Exception: pass
                        continue

                    if is_duplicate and dup_handling == 'discard':
                        logger.info(f"[{config['name']}] RAW: {line} [DROPPED] Cause: DUPLICATE")
                        for cb in list(new_message_callbacks):
                            try: cb({'type': 'ping'})
                            except Exception: pass
                        continue
                        
                    logger.info(f"[{config['name']}] DECODED -> Address: {address}, Alias: {alias}, Msg: {message} {'(DUPLICATE)' if is_duplicate else ''}")
                    
                    alert_match = check_alert_words(message)
                    msg_id, timestamp = save_message(address, message, alias, function_code, f"{protocol_type} {bitrate}".strip(), frequency=freq, is_duplicate=is_duplicate, repeat_count=1, last_timestamp=None)
                    
                    with cache_lock:
                        recent_messages_cache[msg_key] = {
                            'time': now,
                            'id': msg_id,
                            'repeat_count': 1
                        }

                    metadata = {
                        'bitrate': bitrate,
                        'function': function_code,
                        'frequency': freq,
                        'alert_word': alert_match['word'] if alert_match else None,
                        'alert_color': alert_match['color'] if alert_match else None,
                        'sdr_name': config['name'],
                        'is_duplicate': is_duplicate,
                        'repeat_count': 1,
                        'last_timestamp': timestamp
                    }
                    
                    publish_message(address, message, timestamp, alias, metadata=metadata)
                    
                    msg_data = {
                        'type': 'message', 'id': msg_id, 'timestamp': timestamp,
                        'address': address, 'message': message, 'alias': alias,
                        'is_duplicate': is_duplicate,
                        'repeat_count': 1,
                        'last_timestamp': timestamp
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

def normalize_rate_hz(rate_val, default='22050'):
    """Normalizes sample/resample rate inputs like '250k', '250K', '250000' to clean integer string in Hz."""
    if not rate_val:
        return default
    s = str(rate_val).strip()
    try:
        lower = s.lower()
        if lower.endswith('k'):
            return str(int(float(lower[:-1]) * 1000))
        elif lower.endswith('m'):
            return str(int(float(lower[:-1]) * 1000000))
        elif s.isdigit():
            return s
    except (ValueError, TypeError):
        pass
    return s.lower()

def kill_orphaned_rtl_for_device(device_serial):
    """Kills any orphaned rtl_sdr, rtl_fm, rtl_test or tetra_decoder process in the container using this device serial."""
    if not device_serial or os.name != 'posix' or not os.path.exists('/proc'):
        return
    dev_str = str(device_serial).strip()
    if not dev_str:
        return
    try:
        my_pid = os.getpid()
        for pid_dir in os.listdir('/proc'):
            if pid_dir.isdigit() and int(pid_dir) != my_pid:
                cmdline_path = os.path.join('/proc', pid_dir, 'cmdline')
                try:
                    with open(cmdline_path, 'rb') as f:
                        raw = f.read()
                    cmdline = raw.decode('latin-1', errors='ignore')
                    args = cmdline.split('\x00')

                    # Matches rtl_fm, rtl_sdr, rtl_test, or python scripts running tetra_decoder
                    is_target = any(bin_name in cmdline for bin_name in ['rtl_sdr', 'rtl_fm', 'rtl_test', 'tetra_decoder'])
                    if is_target:
                        matches_dev = False
                        for i, arg in enumerate(args):
                            if arg in ('-d', '--device') and i + 1 < len(args) and args[i + 1] == dev_str:
                                matches_dev = True
                                break
                            elif arg.startswith(f"--device={dev_str}") or arg.startswith(f"-d{dev_str}"):
                                matches_dev = True
                                break

                        if matches_dev:
                            logger.warning(f"Dödar föräldralös SDR-process PID {pid_dir} ({args[0] if args else 'proc'}) som låste enhet {dev_str}")
                            try:
                                os.kill(int(pid_dir), signal.SIGKILL)
                            except Exception:
                                pass
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"Fel vid sökning efter föräldralösa processer: {e}")

def normalize_freq(freq_val, default='169.8M'):
    """Normalizes frequency string to remove whitespace and format cleanly for rtl_fm / rtl_sdr."""
    if not freq_val:
        return default
    s = str(freq_val).strip()
    s = re.sub(r'\s+', '', s)
    if not s:
        return default
    # Handle scanning ranges like 390.0M-395.0M or lists
    if any(sep in s for sep in [',', '-', ':']):
        parts = re.split(r'([,\-:])', s)
        return ''.join(normalize_freq(p) if p not in (',', '-', ':') else p for p in parts)
    
    lower = s.lower()
    if lower.endswith('mhz'):
        s = s[:-3] + 'M'
    elif lower.endswith('khz'):
        s = s[:-3] + 'k'
    elif lower.endswith('ghz'):
        s = s[:-3] + 'G'
    elif s.endswith('m'):
        s = s[:-1] + 'M'
    elif s.endswith('K'):
        s = s[:-1] + 'k'
    
    # If pure float/number < 10000 (e.g. 169.8 or 161.4375), user meant MHz
    try:
        val = float(s)
        if 0 < val < 10000:
            return f"{s}M"
    except ValueError:
        pass
        
    return s

def start_instance(config):
    """Starts the subprocesses for a single SDR instance."""
    freq = normalize_freq(config.get('frequency', '169.8M'))
    gain = config.get('gain', 'auto')
    serial = str(config.get('device_serial', '')).strip()
    ppm = config.get('ppm_error', '0')
    sample_rate = normalize_rate_hz(config.get('sample_rate', '22050'), '22050')
    resample_rate = normalize_rate_hz(config.get('resample_rate', '22050'), '22050')
    enable_dc = str(config.get('enable_dc_removal', 'true')).lower() == 'true'
    enable_deemp = str(config.get('enable_deemp', 'true')).lower() == 'true'
    enable_hq_fir = str(config.get('enable_high_quality_fir', 'true')).lower() == 'true'
    atan_math = config.get('atan_math', 'std')
    oversampling = config.get('oversampling', '4')
    
    if serial:
        kill_orphaned_rtl_for_device(serial)
        time.sleep(0.2)

    rtl_cmd = ['rtl_fm', '-f', freq, '-M', 'fm', '-s', sample_rate, '-r', resample_rate]
    if gain and gain != 'auto': rtl_cmd.extend(['-g', str(gain)])
    if ppm and ppm != '0': rtl_cmd.extend(['-p', str(ppm)])
    if enable_dc: rtl_cmd.extend(['-E', 'dc'])
    if enable_deemp: rtl_cmd.extend(['-E', 'deemp'])
    if enable_hq_fir: rtl_cmd.append('-F')
    if atan_math in ['std', 'fast']: rtl_cmd.extend(['-A', atan_math])
    if oversampling and oversampling != '1': rtl_cmd.extend(['-o', oversampling])
    if serial:
        rtl_cmd.extend(['-d', serial])
        logger.info(f"[{config['name']}] Använder specifik SDR-enhet / serienummer: '{serial}'")
    else:
        logger.warning(
            f"[{config['name']}] Inget enhets-ID/serienummer (-d) angivet. "
            f"Om du kör flera mottagare (t.ex. RIKS 1 och RIKS 2) måste du ange unika enhetsindex ('0', '1') "
            f"eller USB-serienummer i inställningarna, annars krockar de om första USB-porten."
        )

    verbosity = config.get('multimon_verbosity', '1')
    charset = config.get('multimon_charset', 'SE')
    fmt = config.get('multimon_format', 'auto')
    inp = config.get('multimon_input_type', 'raw')
    
    protocol = config.get('protocol', 'POCSAG')

    if protocol == 'TETRA':
        # TETRA / RAKEL architecture: rtl_sdr (stream IQ to stdout) | tetra_decoder.py
        # Or standalone scanning mode if frequency range/list is provided
        tetra_sample_rate = config.get('sample_rate', '1800000')
        try:
            if int(tetra_sample_rate) < 1000000:
                tetra_sample_rate = '1800000'
        except (ValueError, TypeError):
            tetra_sample_rate = '1800000'

        tetra_script = os.path.join(os.path.dirname(__file__), 'tetra_decoder.py')
        decoder_cmd = [
            sys.executable, tetra_script,
            '--freq', freq,
            '--sample-rate', str(tetra_sample_rate)
        ]
        if gain and gain != 'auto': decoder_cmd.extend(['--gain', str(gain)])
        if ppm and ppm != '0': decoder_cmd.extend(['--ppm', str(ppm)])
        if serial: decoder_cmd.extend(['--device', serial])

        is_scan = any(sep in freq for sep in [',', '-', ':'])
        if is_scan:
            # Let tetra_decoder.py manage channel scanning and locking
            decoder_cmd.append('--scan')
            logger.info(f"Starting {config['name']} [TETRA SCAN]: {' '.join(decoder_cmd)}")
            p2 = subprocess.Popen(decoder_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            return None, p2

        rtl_cmd = ['rtl_sdr', '-f', freq, '-s', str(tetra_sample_rate)]
        if gain and gain != 'auto': rtl_cmd.extend(['-g', str(gain)])
        if ppm and ppm != '0': rtl_cmd.extend(['-p', str(ppm)])
        if serial: rtl_cmd.extend(['-d', serial])
        rtl_cmd.append('-')

        logger.info(f"Starting {config['name']} [TETRA]: {' '.join(rtl_cmd)} | {' '.join(decoder_cmd)}")
        try:
            p1 = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
            p2 = subprocess.Popen(decoder_cmd, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            p1.stdout.close()
            return p1, p2
        except (FileNotFoundError, OSError):
            logger.warning(f"[{config['name']}] 'rtl_sdr' binary not found on PATH. Running TETRA decoder in standalone mode.")
            p2 = subprocess.Popen(decoder_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            return None, p2
    
    multimon_cmd = [
        'multimon-ng', '-v', verbosity, '-C', charset, '-f', fmt, '-t', inp
    ]

    if protocol == 'AFSK1200':
        multimon_cmd.extend([
            '-a', 'AFSK1200', '-a', 'AFSK2400', '-a', 'AFSK2400_2', '-a', 'AFSK2400_3',
            '-a', 'UFSK1200'
        ])
    else:
        # Default to POCSAG all rates
        multimon_cmd.extend(['-a', 'POCSAG512', '-a', 'POCSAG1200', '-a', 'POCSAG2400'])
    
    multimon_cmd.append('-')

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
        
        serial = inst.get('config', {}).get('device_serial', '')

        # 1. Send SIGTERM first so python decoders can cleanly kill their child rtl processes
        for p in [inst.get('p2'), inst.get('p1')]:
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception: pass
        
        # 2. Wait up to 1.0 second for graceful exit
        for p in [inst.get('p2'), inst.get('p1')]:
            if p and p.poll() is None:
                try:
                    p.wait(timeout=1.0)
                except Exception: pass

        # 3. Force kill with SIGKILL if still lingering
        for p in [inst.get('p2'), inst.get('p1')]:
            if p and p.poll() is None:
                try:
                    p.kill()
                    p.wait(timeout=1.0)
                except Exception: pass

        # 4. Clean up any orphaned child processes that still claim this USB device
        if serial:
            kill_orphaned_rtl_for_device(serial)
        
        del active_instances[instance_id]
        time.sleep(0.4)

def run_sdr_process():
    """Supervisor loop that synchronizes active processes with DB config."""
    logger.info("SDR Supervisor started.")
    last_restart_attempt = {}
    last_heartbeat = 0
    
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
                is_watchdog_restart = False
                if instance_id not in active_instances:
                    should_start = True
                else:
                    inst = active_instances[instance_id]
                    p1 = inst.get('p1')
                    p2 = inst.get('p2')
                    thread = inst.get('thread')
                    
                    p1_dead = p1 is not None and p1.poll() is not None
                    p2_dead = p2 is not None and p2.poll() is not None
                    thread_dead = thread is not None and not thread.is_alive()
                    
                    if p1_dead or p2_dead or thread_dead:
                        p1_code = p1.poll() if p1 else 'N/A'
                        p2_code = p2.poll() if p2 else 'N/A'
                        last_errs = instance_errors.get(instance_id, [])
                        err_detail = f" | Last error: {last_errs[-1]}" if last_errs else ""
                        logger.warning(
                            f"Watchdog: Instance {instance_id} ({db_inst['name']}) died unexpectedly "
                            f"(rtl_fm exit: {p1_code}, multimon exit: {p2_code}, thread_dead={thread_dead}){err_detail}. Cooldown and restarting..."
                        )
                        stop_instance_procs(instance_id)
                        
                        # Throttle restart and give USB subsystem cooldown to release hardware handles
                        last_time = last_restart_attempt.get(instance_id, 0)
                        now = time.time()
                        if now - last_time < 5:
                            time.sleep(2.5)
                        else:
                            time.sleep(1.5)
                        last_restart_attempt[instance_id] = time.time()
                        
                        should_start = True
                        is_watchdog_restart = True
                    else:
                        # Check if config changed
                        active_conf = inst['config']
                        changed = False
                        for k in db_inst.keys():
                            if str(active_conf.get(k)) != str(db_inst.get(k)):
                                changed = True
                                break
                                
                        if changed:
                            logger.info(f"Config change detected for {db_inst['name']}. Restarting...")
                            stop_instance_procs(instance_id)
                            should_start = True
                
                if should_start:
                    p1, p2 = start_instance(db_inst)
                    if p2:
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
                            'thread': monitor_thread,
                            'started_at': time.time()
                        }
                        monitor_thread.start()

                        if is_watchdog_restart:
                            def verify_recovery(inst_id, inst_name, proc1, proc2):
                                # Wait for USB device initialization and startup grace period
                                time.sleep(2.5)
                                proc1_ok = proc1 is None or proc1.poll() is None
                                proc2_ok = proc2 is not None and proc2.poll() is None
                                if proc1_ok and proc2_ok:
                                    p1_pid = proc1.pid if proc1 else 'N/A'
                                    logger.info(f"Watchdog: Instance {inst_id} ({inst_name}) recovered and verified stable (PIDs: rtl={p1_pid}, multimon/decoder={proc2.pid}).")
                                    try:
                                        restart_text = f"Receiver processes died unexpectedly. Instance '{inst_name}' recovered and verified running stably (PID: {p1_pid})."
                                        row_id, timestamp = save_message(
                                            address='SYSTEM',
                                            message=restart_text,
                                            alias=inst_name,
                                            frequency='RESTART',
                                            bitrate='WATCHDOG',
                                            is_protected=False
                                        )
                                        event_payload = {
                                            'id': row_id,
                                            'timestamp': timestamp,
                                            'address': 'SYSTEM',
                                            'alias': inst_name,
                                            'message': restart_text,
                                            'frequency': 'RESTART',
                                            'bitrate': 'WATCHDOG',
                                            'is_duplicate': False,
                                            'is_protected': False,
                                            'is_system': True
                                        }
                                        for cb in list(new_message_callbacks):
                                            try: cb(event_payload)
                                            except Exception: pass
                                    except Exception as e:
                                        logger.error(f"Failed to record watchdog restart event: {e}")
                                else:
                                    p1_ret = proc1.poll() if proc1 else 'N/A'
                                    p2_ret = proc2.poll() if proc2 else 'N/A'
                                    last_err = instance_errors.get(inst_id, [])
                                    err_msg = f": {last_err[-1]}" if last_err else ""
                                    logger.error(
                                        f"Watchdog: Instance {inst_id} ({inst_name}) failed startup health check "
                                        f"(rtl exit: {p1_ret}, decoder exit: {p2_ret}){err_msg}. Will retry on next sync."
                                    )
                                    time.sleep(2.0)
                                    sync_event.set()

                            threading.Thread(target=verify_recovery, args=(instance_id, db_inst['name'], p1, p2), daemon=True).start()
                    else:
                        logger.error(f"Failed to start {db_inst['name']}. Retrying next sync.")

            # 3. Periodic supervisor heartbeat every 60 seconds (compact summary)
            now = time.time()
            if now - last_heartbeat >= 60:
                last_heartbeat = now
                status_parts = []
                for db_inst in instances_from_db:
                    inst_id = db_inst['id']
                    name = db_inst['name']
                    enabled = db_inst.get('enabled', 1)
                    if not enabled:
                        continue
                    
                    inst = active_instances.get(inst_id)
                    if not inst:
                        status_parts.append(f"[{name}] VANTAR")
                        continue
                        
                    p1 = inst.get('p1')
                    p2 = inst.get('p2')
                    p1_running = p1 is None or p1.poll() is None
                    p2_running = p2 is not None and p2.poll() is None
                    
                    if p1_running and p2_running:
                        last_rec = inst.get('last_message_time')
                        if last_rec:
                            elapsed = int(now - last_rec)
                            ago = f"{elapsed}s" if elapsed < 60 else f"{elapsed // 60}m"
                            status_parts.append(f"[{name}] OK ({ago})")
                        else:
                            status_parts.append(f"[{name}] OK (lyssnar)")
                    else:
                        dead = []
                        if p1 is not None and p1.poll() is not None: dead.append("rtl")
                        if not p2_running: dead.append("decoder")
                        status_parts.append(f"[{name}] FEL ({'+'.join(dead)} dod)")
                
                if status_parts:
                    logger.info(f"SDR Heartbeat: {' | '.join(status_parts)}")

        except Exception as e:
            logger.error(f"Error in supervisor loop: {e}")
        
        # Wait for either a sync event (settings saved) or periodic check
        sync_event.wait(timeout=10)

def get_sdr_runtime_status():
    """Returns a dict of runtime status for all active instances."""
    status = {}
    now = time.time()
    for inst_id, inst in list(active_instances.items()):
        p1 = inst.get('p1')
        p2 = inst.get('p2')
        p1_running = p1 is None or p1.poll() is None
        p2_running = p2 is not None and p2.poll() is None
        errs = instance_errors.get(inst_id, [])
        last_rec = inst.get('last_message_time')
        
        status[inst_id] = {
            'is_running': p1_running and p2_running,
            'rtl_fm_pid': p1.pid if (p1 and p1.poll() is None) else None,
            'multimon_pid': p2.pid if p2_running else None,
            'started_at': inst.get('started_at'),
            'uptime_seconds': int(now - inst.get('started_at', now)),
            'last_message_time': last_rec,
            'last_message_age_seconds': int(now - last_rec) if last_rec else None,
            'last_error': errs[-1] if errs else None
        }
    return status

def start_sdr_thread():
    global sdr_thread
    if not sdr_thread or not sdr_thread.is_alive():
        sdr_thread = threading.Thread(target=run_sdr_process, daemon=True)
        sdr_thread.start()

def restart_sdr():
    """Trigger the supervisor to re-sync with the database."""
    logger.info("Sync requested for Multi-SDR supervisor.")
    sync_event.set()
