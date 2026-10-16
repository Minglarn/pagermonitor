import sqlite3
import os
import re
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'messages.db')

def extract_body_for_alert_matching(text):
    """
    Extraherar den faktiska meddelandebrödtexten för larmordsmatchning.
    Rensar bort:
    1. Dold rådata (allt från Rådata: till slutet) så att JSON-nycklar/värden som "SafetyNet" inte triggar larmord.
    2. Syntetiska metadatarubriker inom klamrar (t.ex. [Inmarsat STD-C ...] Prioritet: Safety) överst.
    """
    if not text:
        return ""
    s = str(text)
    # Klipp bort Rådata
    m_raw = re.search(r'(?:\r?\n|\s*\|\s*)Rådata:\s*', s, re.IGNORECASE)
    if m_raw:
        s = s[:m_raw.start()]
    else:
        m_raw2 = re.search(r'\bRådata:\s*', s, re.IGNORECASE)
        if m_raw2:
            s = s[:m_raw2.start()]

    # Klipp bort syntetiska huvuden t.ex. [Inmarsat STD-C / ...] ... \n
    s = re.sub(
        r'^\[(?:Inmarsat|EGC|STD-C|SafetyNET|FleetNET|SAR|Upprop|Kanalallokering|Bulletin Board|Signalling Channel|Kontrollpaket)[^\]\n]*\][^\n]*\r?\n?',
        '',
        s,
        flags=re.IGNORECASE
    )
    return s.strip()

def regex_word_match(pattern, text):
    if not pattern or not text:
        return 0
    clean_text = extract_body_for_alert_matching(text)
    if not clean_text:
        return 0
    # Match whole word with word boundary (Unicode-aware for Swedish characters)
    regex = rf'(?<![a-zA-Z0-9åäöÅÄÖ]){re.escape(str(pattern))}(?![a-zA-Z0-9åäöÅÄÖ])'
    return 1 if re.search(regex, clean_text, re.IGNORECASE) else 0

def get_connection(timeout=30.0):
    """Create a sqlite3 connection with WAL mode, busy timeout, and Unicode-aware helper functions."""
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.create_function("UPPER_UNICODE", 1, lambda s: (s or '').upper())
    conn.create_function("WORD_MATCH", 2, regex_word_match)
    return conn


def get_default_settings():
    return {
        'frequency': '169.8M',
        'gain': '25',
        'device_serial': '',
        'multimon_verbosity': '2',
        'multimon_charset': 'SE',
        'multimon_format': 'auto',
        'message_font': 'JetBrains Mono',
        'message_font_size': '1.0',
        'sample_rate': '250000',
        'resample_rate': '22050',
        'enable_dc_removal': 'true',
        'enable_deemp': 'true',
        'enable_high_quality_fir': 'false',
        'atan_math': 'std',
        'oversampling': '4',
        'ppm_error': '0',
        'multimon_input_type': 'raw',
        'garbage_filter': 'true',
        'garbage_filter_sensitivity': '50',
        'duplicate_handling': 'merge',
        'duplicate_window': '120',
        'save_duplicates': 'true',
        'auto_prune_enabled': 'true',
        'auto_prune_days': '30',
        'log_tetra_basestations': 'true',
        'tetra_scan_mode': 'monitor',
        'tetra_dwell_time': '60',
        'tetra_skip_encrypted': 'false',
        'rds_heartbeat_interval': '10',
        'rds_heartbeat_timeout': '5',
        'vdl2_enabled': 'true',
        'vdl2_host': '192.168.1.242',
        'vdl2_port': '15555',
        'vdl2_filter_empty': 'true',
        'vdl2_filter_links': 'false',
        'sonde_enabled': 'true',
        'sonde_udp_port': '55673',
        'sonde_db_interval': '5',
        'satc_enabled': 'true',
        'satc_host': '0.0.0.0',
        'satc_port': '6558',
        'satc_only_messages': 'true',
        'hfdl_enabled': 'false',
        'hfdl_host': '127.0.0.1',
        'hfdl_port': '15556',
        'hfdl_only_messages': 'true'
    }

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            address TEXT NOT NULL,
            message TEXT NOT NULL,
            alias TEXT DEFAULT '',
            function_code INTEGER DEFAULT 0,
            bitrate TEXT DEFAULT '',
            frequency TEXT DEFAULT '',
            is_duplicate INTEGER DEFAULT 0,
            is_protected INTEGER DEFAULT 0,
            repeat_count INTEGER DEFAULT 1,
            last_timestamp TEXT DEFAULT ''
        )
    ''')
    
    # Try adding columns to existing messages table
    for col, type_info in [
        ('alias', 'TEXT DEFAULT ""'),
        ('function_code', 'INTEGER DEFAULT 0'),
        ('bitrate', 'TEXT DEFAULT ""'),
        ('frequency', 'TEXT DEFAULT ""'),
        ('is_duplicate', 'INTEGER DEFAULT 0'),
        ('is_protected', 'INTEGER DEFAULT 0'),
        ('repeat_count', 'INTEGER DEFAULT 1'),
        ('last_timestamp', 'TEXT DEFAULT ""'),
        ('metadata', 'TEXT DEFAULT ""')
    ]:
        try:
            c.execute(f'ALTER TABLE messages ADD COLUMN {col} {type_info}')
        except sqlite3.OperationalError:
            pass # Column might already exist
    
    # Create indexes for high-speed queries on large datasets
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_id_desc ON messages(id DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_address ON messages(address)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_is_duplicate ON messages(is_duplicate)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_is_protected ON messages(is_protected)')

    # Create settings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Create aliases table
    c.execute('''
        CREATE TABLE IF NOT EXISTS aliases (
            address TEXT PRIMARY KEY,
            alias TEXT NOT NULL,
            is_hidden INTEGER DEFAULT 0
        )
    ''')

    # Create alert_words table
    c.execute('''
        CREATE TABLE IF NOT EXISTS alert_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            color TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Try adding is_hidden column to existing table to support migrations
    try:
        c.execute('ALTER TABLE aliases ADD COLUMN is_hidden INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass # Column might already exist
    
    # Create sdr_instances table
    c.execute('''
        CREATE TABLE IF NOT EXISTS sdr_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            frequency TEXT NOT NULL,
            gain TEXT DEFAULT '25',
            device_serial TEXT DEFAULT '',
            ppm_error TEXT DEFAULT '0',
            sample_rate TEXT DEFAULT '250000',
            resample_rate TEXT DEFAULT '22050',
            enable_dc_removal TEXT DEFAULT 'true',
            enable_deemp TEXT DEFAULT 'true',
            enable_high_quality_fir TEXT DEFAULT 'false',
            atan_math TEXT DEFAULT 'std',
            oversampling TEXT DEFAULT '4',
            multimon_verbosity TEXT DEFAULT '2',
            multimon_charset TEXT DEFAULT 'SE',
            multimon_format TEXT DEFAULT 'auto',
            multimon_input_type TEXT DEFAULT 'raw',
            protocol TEXT DEFAULT 'POCSAG',
            tetra_mode TEXT DEFAULT 'monitor',
            tetra_dwell_time TEXT DEFAULT '60',
            tetra_skip_encrypted TEXT DEFAULT 'false',
            enabled INTEGER DEFAULT 1
        )
    ''')

    # Run migrations for sdr_instances columns if they don't exist
    for col, type_info in [
        ('enable_high_quality_fir', 'TEXT DEFAULT "false"'),
        ('atan_math', 'TEXT DEFAULT "std"'),
        ('oversampling', 'TEXT DEFAULT "4"'),
        ('protocol', 'TEXT DEFAULT "POCSAG"'),
        ('tetra_mode', 'TEXT DEFAULT "monitor"'),
        ('tetra_dwell_time', 'TEXT DEFAULT "60"'),
        ('tetra_skip_encrypted', 'TEXT DEFAULT "false"')
    ]:
        try:
            c.execute(f'ALTER TABLE sdr_instances ADD COLUMN {col} {type_info}')
        except sqlite3.OperationalError:
            pass # Column already exists
    
    # Initialize default settings if they don't exist
    defaults = get_default_settings()
    for key, val in defaults.items():
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))
    c.execute("UPDATE settings SET value='true' WHERE key='log_tetra_basestations' AND value='false'")
    c.execute("UPDATE settings SET value='6558' WHERE key='satc_port' AND value='5558'")
    # Rensa automatiskt bort eventuella vanliga RDS-meddelanden (t.ex. låttexter från kommersiella FM-stationer)
    try:
        c.execute("DELETE FROM messages WHERE bitrate = 'RDS-PS' OR address LIKE 'RDS-%'")
    except Exception:
        pass

    # Rensa bort eventuella sparade pratbubbel-emojis i meddelandetext
    try:
        c.execute("UPDATE messages SET message = REPLACE(message, '\U0001f4ac ', '') WHERE message LIKE '%\U0001f4ac%'")
        c.execute("UPDATE messages SET message = REPLACE(message, '\U0001f4ac', '') WHERE message LIKE '%\U0001f4ac%'")
    except Exception:
        pass

    # Migration: If sdr_instances is empty, create the first instance from current settings
    c.execute('SELECT COUNT(*) FROM sdr_instances')
    if c.fetchone()[0] == 0:
        logger.info("Migrating existing SDR settings to sdr_instances table...")
        # Fetch current settings from the settings table
        c.execute('SELECT key, value FROM settings')
        current_settings = dict(c.fetchall())
        
        # Merge with defaults to ensure all keys exist
        full_settings = {**defaults, **current_settings}
        
        c.execute('''
            INSERT INTO sdr_instances (
                name, frequency, gain, device_serial, ppm_error, 
                sample_rate, resample_rate, enable_dc_removal, enable_deemp,
                enable_high_quality_fir, atan_math, oversampling,
                multimon_verbosity, multimon_charset, multimon_format, 
                multimon_input_type, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            "Standard-mottagare",
            full_settings.get('frequency', '169.8M'),
            full_settings.get('gain', 'auto'),
            full_settings.get('device_serial', ''),
            full_settings.get('ppm_error', '0'),
            full_settings.get('sample_rate', '22050'),
            full_settings.get('resample_rate', '22050'),
            full_settings.get('enable_dc_removal', 'true'),
            full_settings.get('enable_deemp', 'true'),
            full_settings.get('enable_high_quality_fir', 'false'),
            full_settings.get('atan_math', 'std'),
            full_settings.get('oversampling', '4'),
            full_settings.get('multimon_verbosity', '1'),
            full_settings.get('multimon_charset', 'SE'),
            full_settings.get('multimon_format', 'auto'),
            full_settings.get('multimon_input_type', 'raw'),
            1
        ))
        
    # One-time re-indexing check
    c.execute('SELECT value FROM settings WHERE key = ?', ('db_reindexed',))
    reindexed = c.fetchone()
    if not reindexed:
        # Check if there are messages to re-index
        c.execute('SELECT COUNT(*) FROM messages')
        count_row = c.fetchone()
        if count_row and count_row[0] > 0:
            logger.info("One-time database re-indexing starting...")
            reindex_messages(conn)
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('db_reindexed', 'true'))
            logger.info("One-time database re-indexing completed.")
        else:
            # Empty DB, just mark as done
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('db_reindexed', 'true'))

    conn.commit()
    conn.close()

def save_message(address, message, alias='', function_code=0, bitrate='', frequency='', is_duplicate=False, is_protected=False, repeat_count=1, last_timestamp=None, metadata=None):
    if message:
        message = str(message).replace('\U0001f4ac ', '').replace('\U0001f4ac', '')
    if is_duplicate:
        settings = get_settings()
        save_dups = settings.get('save_duplicates', 'true') in ('true', '1', True)
        dup_handling = settings.get('duplicate_handling', 'merge')
        if not save_dups or dup_handling == 'discard':
            return None, None

    conn = get_connection()
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    if last_timestamp is None:
        last_timestamp = timestamp
    meta_json = ""
    if metadata:
        try:
            import json
            meta_json = json.dumps(metadata)
        except Exception:
            pass
    try:
        c.execute('''
            INSERT INTO messages (timestamp, address, message, alias, function_code, bitrate, frequency, is_duplicate, is_protected, repeat_count, last_timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, address, message, alias, function_code, bitrate, frequency, 1 if is_duplicate else 0, 1 if is_protected else 0, repeat_count, last_timestamp, meta_json))
    except sqlite3.OperationalError:
        c.execute('''
            INSERT INTO messages (timestamp, address, message, alias, function_code, bitrate, frequency, is_duplicate, is_protected, repeat_count, last_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, address, message, alias, function_code, bitrate, frequency, 1 if is_duplicate else 0, 1 if is_protected else 0, repeat_count, last_timestamp))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id, timestamp

def increment_message_repeat(msg_id, last_timestamp=None):
    """Increments repeat_count and updates last_timestamp on an existing message."""
    if not last_timestamp:
        last_timestamp = datetime.now().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE messages
        SET repeat_count = COALESCE(repeat_count, 1) + 1,
            last_timestamp = ?
        WHERE id = ?
    ''', (last_timestamp, msg_id))
    conn.commit()
    c.execute('SELECT repeat_count FROM messages WHERE id = ?', (msg_id,))
    row = c.fetchone()
    count = row[0] if row else 1
    conn.close()
    return count

def toggle_message_lock(msg_id, protected):
    """Toggle the protected/locked status of a message."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE messages SET is_protected = ? WHERE id = ?', (1 if protected else 0, msg_id))
    conn.commit()
    conn.close()

def delete_message(msg_id):
    """Delete a specific message by ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()

def reindex_messages(already_open_conn=None):
    """Resets message IDs to be sequential starting from 1 (One-time operation)."""
    conn = already_open_conn if already_open_conn else sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Create temporary table with same schema
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            address TEXT NOT NULL,
            message TEXT NOT NULL,
            alias TEXT DEFAULT '',
            function_code INTEGER DEFAULT 0,
            bitrate TEXT DEFAULT '',
            frequency TEXT DEFAULT '',
            is_duplicate INTEGER DEFAULT 0,
            is_protected INTEGER DEFAULT 0,
            repeat_count INTEGER DEFAULT 1,
            last_timestamp TEXT DEFAULT ''
        )
    ''')
    
    # 2. Copy data ordered by timestamp (or old id)
    c.execute('''
        INSERT INTO messages_new (timestamp, address, message, alias, function_code, bitrate, frequency, is_duplicate, is_protected, repeat_count, last_timestamp)
        SELECT timestamp, address, message, alias, function_code, bitrate, frequency, is_duplicate, is_protected, COALESCE(repeat_count, 1), COALESCE(last_timestamp, timestamp)
        FROM messages ORDER BY timestamp ASC
    ''')
    
    # 3. Swap tables
    c.execute('DROP TABLE messages')
    c.execute('ALTER TABLE messages_new RENAME TO messages')
    
    if not already_open_conn:
        conn.commit()
        conn.close()

def get_recent_messages(limit=None, before_id=None, since_id=None, search=None, alerts_only=False, exclude_duplicates=False, protocol=None, ensure_active_protocols=False):
    conn = get_connection()
    c = conn.cursor()
    
    # Check if we have the is_hidden column in aliases
    c.execute('PRAGMA table_info(aliases)')
    columns = [col[1] for col in c.fetchall()]
    has_hidden = 'is_hidden' in columns
    
    base_query = '''
        SELECT m.*, a.alias as current_alias FROM messages m
        LEFT JOIN aliases a ON m.address = a.address
    '''
    
    where_clauses = []
    params = []
    
    if has_hidden:
        where_clauses.append('(a.is_hidden IS NULL OR a.is_hidden = 0)')
        
    if exclude_duplicates:
        where_clauses.append('(m.is_duplicate IS NULL OR m.is_duplicate = 0)')
        
    if alerts_only:
        where_clauses.append('''
            EXISTS (
                SELECT 1 FROM alert_words aw
                WHERE aw.is_active = 1
                AND WORD_MATCH(aw.word, m.message) = 1
            )
        ''')

    if protocol:
        p_up = str(protocol).strip().upper()
        if p_up in ('SATC', 'INMARSAT'):
            where_clauses.append("(m.bitrate LIKE '%SATC%' OR m.bitrate LIKE '%INMARSAT%' OR m.address LIKE 'SATC%' OR m.address LIKE 'LES:%')")
        elif p_up in ('VDL2', 'VDL', 'ACARS'):
            where_clauses.append("(m.bitrate LIKE '%VDL%' OR m.bitrate LIKE '%ACARS%')")
        elif p_up == 'HFDL':
            where_clauses.append("(m.bitrate LIKE '%HFDL%')")
        elif p_up == 'SONDE':
            where_clauses.append("(m.bitrate LIKE '%SONDE%')")
        elif p_up == 'TETRA':
            where_clauses.append("(m.bitrate LIKE '%TETRA%' OR m.address LIKE 'RAKEL-%' OR m.address LIKE 'TETRA-%')")
        elif p_up in ('RDS', 'TMC', 'RDS-TMC'):
            where_clauses.append("(m.bitrate LIKE '%RDS%' OR m.bitrate LIKE '%TMC%' OR m.address LIKE 'E4:%' OR m.address LIKE 'TMC-%')")
        elif p_up == 'AFSK':
            where_clauses.append("(m.bitrate LIKE '%AFSK%' OR m.bitrate LIKE '%UFSK%' OR m.address = 'AFSK')")
        elif p_up == 'POCSAG':
            where_clauses.append("(m.bitrate LIKE '%POCSAG%' OR (m.bitrate GLOB '[0-9]*' AND m.bitrate != '') OR m.address GLOB '[0-9]*')")

    if before_id:
        where_clauses.append('m.id < ?')
        params.append(before_id)
        
    if since_id:
        where_clauses.append('m.id > ?')
        params.append(since_id)
        
    if search:
        search_term = f'%{search}%' # For LIKE
        where_clauses.append('''
            (m.message LIKE ? OR m.address LIKE ? OR a.alias LIKE ? OR m.timestamp LIKE ?)
        ''')
        params.extend([search_term, search_term, search_term, search_term])
        
    query = base_query
    if where_clauses:
        query += ' WHERE ' + ' AND '.join(where_clauses)
        
    query += ' ORDER BY m.id DESC'
    if limit is not None and limit > 0:
        query += ' LIMIT ?'
        params.append(limit)
        
    c.execute(query, tuple(params))
    rows = c.fetchall()
    
    # Detect position by reading description
    col_names = [description[0] for description in c.description]
    id_idx = col_names.index('id')
    ts_idx = col_names.index('timestamp')
    addr_idx = col_names.index('address')
    msg_idx = col_names.index('message')
    alias_idx = col_names.index('alias') if 'alias' in col_names else -1
    curr_alias_idx = col_names.index('current_alias') if 'current_alias' in col_names else -1

    conn.close()
    
    messages = []
    for row in rows:
        saved_alias = row[alias_idx] if alias_idx != -1 else ''
        curr_alias = row[curr_alias_idx] if curr_alias_idx != -1 else None

        msg = {
            'id': row[id_idx],
            'timestamp': row[ts_idx],
            'address': row[addr_idx],
            'message': row[msg_idx],
            'alias': curr_alias if curr_alias is not None else saved_alias
        }
        # Add metadata if exists
        if 'function_code' in col_names:
            msg['function_code'] = row[col_names.index('function_code')]
        if 'bitrate' in col_names:
            msg['bitrate'] = row[col_names.index('bitrate')]
            b_val = str(msg['bitrate'] or '').strip()
            if 'TETRA' in b_val or str(msg['address']).startswith('RAKEL-') or str(msg['address']).startswith('TETRA-'):
                msg['protocol'] = 'TETRA'
            elif 'RDS' in b_val or 'TMC' in b_val or str(msg['address']).startswith('E4:') or str(msg['address']).startswith('TMC-'):
                msg['protocol'] = 'RDS-TMC'
            elif 'VDL' in b_val or 'ACARS' in b_val:
                msg['protocol'] = 'VDL2'
            elif 'SONDE' in b_val:
                msg['protocol'] = 'SONDE'
            elif 'HFDL' in b_val:
                msg['protocol'] = 'HFDL'
            elif 'SATC' in b_val or 'INMARSAT' in b_val or str(msg['address']).startswith('SATC') or str(msg['address']).startswith('LES:'):
                msg['protocol'] = 'SATC'
            elif 'AFSK' in b_val or 'UFSK' in b_val or msg['address'] == 'AFSK':
                msg['protocol'] = 'AFSK'
            elif 'POCSAG' in b_val or b_val.isdigit() or str(msg['address']).isdigit():
                msg['protocol'] = 'POCSAG'
        if 'frequency' in col_names:
            msg['frequency'] = row[col_names.index('frequency')]
        if 'is_duplicate' in col_names:
            msg['is_duplicate'] = bool(row[col_names.index('is_duplicate')])
        if 'is_protected' in col_names:
            msg['is_protected'] = bool(row[col_names.index('is_protected')])
        if 'repeat_count' in col_names:
            msg['repeat_count'] = row[col_names.index('repeat_count')] or 1
        else:
            msg['repeat_count'] = 1
        if 'last_timestamp' in col_names:
            msg['last_timestamp'] = row[col_names.index('last_timestamp')] or ''
        else:
            msg['last_timestamp'] = ''
        if 'metadata' in col_names and row[col_names.index('metadata')]:
            try:
                import json
                m_obj = json.loads(row[col_names.index('metadata')])
                if isinstance(m_obj, dict):
                    for k, v in m_obj.items():
                        if k not in msg and v is not None:
                            msg[k] = v
            except Exception:
                pass
            
        messages.append(msg)

    if ensure_active_protocols and limit and limit > 0:
        proto_counts = {}
        for m in messages:
            p = m.get('protocol') or 'POCSAG'
            proto_counts[p] = proto_counts.get(p, 0) + 1

        existing_ids = {m['id'] for m in messages}
        important_protos = ['SATC', 'HFDL', 'SONDE', 'POCSAG', 'VDL2']
        for p_name in important_protos:
            if proto_counts.get(p_name, 0) < 20:
                extra = get_recent_messages(
                    limit=50,
                    alerts_only=alerts_only,
                    exclude_duplicates=exclude_duplicates,
                    protocol=p_name,
                    ensure_active_protocols=False
                )
                for em in extra:
                    if em['id'] not in existing_ids:
                        messages.append(em)
                        existing_ids.add(em['id'])
        messages.sort(key=lambda x: x['id'], reverse=True)

    return messages

def get_alert_words():
    """Retrieve all alert words."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Ensure table exists in case container wasn't restarted after update
    c.execute('''
        CREATE TABLE IF NOT EXISTS alert_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            color TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    c.execute('SELECT id, word, color, is_active FROM alert_words')
    rows = c.fetchall()
    conn.close()
    
    alerts = []
    for id_val, word, color, is_active in rows:
        alerts.append({
            'id': id_val,
            'word': word,
            'color': color,
            'is_active': bool(is_active)
        })
    return alerts

def check_alert_words(message):
    """Scan a message for active alert words and return the first match (word, color) or None.
    Matches ONLY whole words using Unicode-aware word boundaries.
    """
    if not message:
        return None
    body_text = extract_body_for_alert_matching(message)
    if not body_text:
        return None
    alerts = get_alert_words()
    # Sort by length descending to match longest word first (standard practice)
    alerts.sort(key=lambda x: len(x['word']), reverse=True)
    
    msg_str = body_text
    for alert in alerts:
        if not alert['is_active'] or not alert.get('word'):
            continue
        word = str(alert['word']).strip()
        if not word:
            continue
        # Helordsmatchning som hindrar att t.ex. 'LIGHT' matchar inuti 'Flight'
        pattern = rf'(?<![a-zA-Z0-9åäöÅÄÖ]){re.escape(word)}(?![a-zA-Z0-9åäöÅÄÖ])'
        if re.search(pattern, msg_str, re.IGNORECASE):
            return {
                'word': alert['word'],
                'color': alert['color']
            }
    return None

def save_alert_word(word, color, is_active=True):
    """Create or update an alert word."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Ensure table exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS alert_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            color TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    c.execute('INSERT OR REPLACE INTO alert_words (word, color, is_active) VALUES (?, ?, ?)',
              (word, color, 1 if is_active else 0))
    conn.commit()
    conn.close()

def delete_alert_word(word_id):
    """Delete an alert word by ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM alert_words WHERE id = ?', (word_id,))
    conn.commit()
    conn.close()

def get_settings():
    """Retrieve all settings as a dictionary merged with default fallback settings."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT key, value FROM settings')
    rows = c.fetchall()
    conn.close()
    
    settings = get_default_settings()
    for key, value in rows:
        settings[key] = value
    return settings

def update_setting(key, value):
    """Update a specific setting, inserting if it does not already exist."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

def get_aliases():
    """Retrieve all CapCode aliases."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if is_hidden column exists (for older DB versions querying)
    c.execute('PRAGMA table_info(aliases)')
    columns = [col[1] for col in c.fetchall()]
    
    if 'is_hidden' in columns:
        c.execute('SELECT address, alias, is_hidden FROM aliases')
    else:
        c.execute('SELECT address, alias, 0 as is_hidden FROM aliases')
        
    rows = c.fetchall()
    conn.close()
    
    aliases = {}
    for addr, alias, is_hidden in rows:
        aliases[addr] = {'alias': alias, 'is_hidden': bool(is_hidden)}
    return aliases

def get_alias_info(address):
    """Retrieve alias info for a specific address. Returns dict or None."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get column info
    c.execute('PRAGMA table_info(aliases)')
    columns = [col[1] for col in c.fetchall()]
    has_hidden = 'is_hidden' in columns
    
    if has_hidden:
        c.execute('SELECT alias, is_hidden FROM aliases WHERE address = ?', (address,))
    else:
        c.execute('SELECT alias, 0 as is_hidden FROM aliases WHERE address = ?', (address,))
        
    row = c.fetchone()
    conn.close()
    
    if row:
        return {'alias': row[0], 'is_hidden': bool(row[1])}
    return None

def save_alias(address, alias, is_hidden=False):
    """Create or update an alias."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO aliases (address, alias, is_hidden) VALUES (?, ?, ?)', 
              (address, alias, 1 if is_hidden else 0))
    conn.commit()
    conn.close()

def delete_alias(address):
    """Delete an alias."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM aliases WHERE address = ?', (address,))
    conn.commit()
    conn.close()

def get_sdr_instances():
    """Retrieve all hardware profiles."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Run migrations for settings if they don't exist
    for col, type_info in [
        ('enable_high_quality_fir', 'TEXT DEFAULT "false"'),
        ('atan_math', 'TEXT DEFAULT "std"'),
        ('oversampling', 'TEXT DEFAULT "4"'),
        ('protocol', 'TEXT DEFAULT "POCSAG"'),
        ('tetra_mode', 'TEXT DEFAULT "monitor"'),
        ('tetra_dwell_time', 'TEXT DEFAULT "60"'),
        ('tetra_skip_encrypted', 'TEXT DEFAULT "false"')
    ]:
        try:
            c.execute(f'ALTER TABLE sdr_instances ADD COLUMN {col} {type_info}')
        except sqlite3.OperationalError:
            pass # Column already exists

    c.execute('SELECT * FROM sdr_instances')
    rows = c.fetchall()
    
    col_names = [description[0] for description in c.description]
    conn.close()
    
    instances = []
    for row in rows:
        instance = {}
        for i, col in enumerate(col_names):
            instance[col] = row[i]
        instances.append(instance)
    return instances

def save_sdr_instance(data):
    """Create or update an SDR hardware profile."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    instance_id = data.get('id')
    name = str(data.get('name', 'Ny mottagare')).strip()
    protocol = data.get('protocol', 'POCSAG')
    raw_freq = str(data.get('frequency', '')).strip()
    if not raw_freq or raw_freq.lower() in ('auto', 'scan'):
        freq = 'auto' if protocol == 'RDS-TMC' else ('390M-395M' if protocol == 'TETRA' else '169.8M')
    else:
        freq = re.sub(r'\s+', '', raw_freq)
    gain = str(data.get('gain', 'auto')).strip()
    serial = str(data.get('device_serial', '')).strip()
    ppm = data.get('ppm_error', '0')
    sample_rate = data.get('sample_rate', '22050')
    resample_rate = data.get('resample_rate', '22050')
    dc = data.get('enable_dc_removal', 'true')
    deemp = data.get('enable_deemp', 'true')
    hq_fir = data.get('enable_high_quality_fir', 'true')
    atan = data.get('atan_math', 'std')
    oversamp = data.get('oversampling', '4')
    verb = data.get('multimon_verbosity', '2')
    charset = data.get('multimon_charset', 'SE')
    fmt = data.get('multimon_format', 'auto')
    inp = data.get('multimon_input_type', 'raw')
    protocol = data.get('protocol', 'POCSAG')
    tetra_mode = str(data.get('tetra_mode', 'monitor')).strip()
    tetra_dwell_time = str(data.get('tetra_dwell_time', '60')).strip()
    tetra_skip_encrypted = str(data.get('tetra_skip_encrypted', 'false')).strip()
    enabled = data.get('enabled', 1)

    if instance_id:
        c.execute('''
            UPDATE sdr_instances SET 
                name=?, frequency=?, gain=?, device_serial=?, ppm_error=?,
                sample_rate=?, resample_rate=?, enable_dc_removal=?, enable_deemp=?,
                enable_high_quality_fir=?, atan_math=?, oversampling=?,
                multimon_verbosity=?, multimon_charset=?, multimon_format=?,
                multimon_input_type=?, protocol=?, tetra_mode=?, tetra_dwell_time=?, tetra_skip_encrypted=?, enabled=?
            WHERE id=?
        ''', (name, freq, gain, serial, ppm, sample_rate, resample_rate, dc, deemp, hq_fir, atan, oversamp, verb, charset, fmt, inp, protocol, tetra_mode, tetra_dwell_time, tetra_skip_encrypted, enabled, instance_id))
    else:
        c.execute('''
            INSERT INTO sdr_instances (
                name, frequency, gain, device_serial, ppm_error,
                sample_rate, resample_rate, enable_dc_removal, enable_deemp,
                enable_high_quality_fir, atan_math, oversampling,
                multimon_verbosity, multimon_charset, multimon_format,
                multimon_input_type, protocol, tetra_mode, tetra_dwell_time, tetra_skip_encrypted, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, freq, gain, serial, ppm, sample_rate, resample_rate, dc, deemp, hq_fir, atan, oversamp, verb, charset, fmt, inp, protocol, tetra_mode, tetra_dwell_time, tetra_skip_encrypted, 1))
        
    conn.commit()
    conn.close()

def delete_sdr_instance(instance_id):
    """Remove a hardware profile."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM sdr_instances WHERE id = ?', (instance_id,))
    conn.commit()
    conn.close()

def toggle_sdr_instance(instance_id, enabled):
    """Enable or disable an SDR instance."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE sdr_instances SET enabled = ? WHERE id = ?', (1 if enabled else 0, instance_id))
    conn.commit()
    conn.close()

def clone_sdr_instance(source_id, new_name=None, new_frequency=None, enabled=0):
    """Clone an existing SDR hardware profile with all settings preserved."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM sdr_instances WHERE id = ?', (source_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    
    source = dict(row)
    name = (new_name or f"{source.get('name', 'Receiver')} (Copy)").strip()
    frequency = (new_frequency or source.get('frequency', '169.8M')).strip()
    
    c.execute('''
        INSERT INTO sdr_instances (
            name, frequency, gain, device_serial, ppm_error,
            sample_rate, resample_rate, enable_dc_removal, enable_deemp,
            enable_high_quality_fir, atan_math, oversampling,
            multimon_verbosity, multimon_charset, multimon_format,
            multimon_input_type, protocol, tetra_mode, tetra_dwell_time, tetra_skip_encrypted, enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        name,
        frequency,
        source.get('gain', 'auto'),
        source.get('device_serial', ''),
        source.get('ppm_error', '0'),
        source.get('sample_rate', '250000'),
        source.get('resample_rate', '22050'),
        source.get('enable_dc_removal', 'true'),
        source.get('enable_deemp', 'true'),
        source.get('enable_high_quality_fir', 'false'),
        source.get('atan_math', 'std'),
        source.get('oversampling', '4'),
        source.get('multimon_verbosity', '2'),
        source.get('multimon_charset', 'SE'),
        source.get('multimon_format', 'auto'),
        source.get('multimon_input_type', 'raw'),
        source.get('protocol', 'POCSAG'),
        source.get('tetra_mode', 'monitor'),
        source.get('tetra_dwell_time', '60'),
        source.get('tetra_skip_encrypted', 'false'),
        1 if enabled else 0
    ))
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id

def get_db_connection():
    """Returns a new sqlite3 connection to DB_PATH."""
    return sqlite3.connect(DB_PATH)

def clear_basestation_messages():
    """Delete all non-protected TETRA base station announcement rows."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("""
            DELETE FROM messages 
            WHERE (bitrate LIKE '%TETRA-NET%' OR message LIKE '%Aktiv TETRA Basstation%' OR message LIKE '%Aktiv Basstation på%' OR address LIKE 'RAKEL-%') 
            AND (is_protected IS NULL OR is_protected = 0)
        """)
        deleted_count = c.rowcount
        conn.commit()
        return deleted_count
    finally:
        conn.close()

def clear_messages():
    """Delete all messages from the database."""
    conn = get_connection(timeout=60.0)
    try:
        c = conn.cursor()
        c.execute('DELETE FROM messages')
        conn.commit()
        conn.isolation_level = None
        c.execute('VACUUM')
        invalidate_database_stats_cache()
    finally:
        conn.close()

def prune_messages(days):
    """Delete messages older than X days, except protected ones."""
    conn = get_connection(timeout=60.0)
    try:
        c = conn.cursor()
        # Replace 'T' with space and use 'localtime' for accurate timestamp comparison
        c.execute("""
            DELETE FROM messages 
            WHERE datetime(replace(timestamp, 'T', ' ')) <= datetime('now', 'localtime', '-' || ? || ' days') 
            AND (is_protected IS NULL OR is_protected = 0)
        """, (days,))
        deleted_count = c.rowcount
        conn.commit()
        if deleted_count > 0:
            invalidate_database_stats_cache()
            try:
                conn.isolation_level = None
                c.execute('VACUUM')
            except Exception as ve:
                logger.warning(f"Vacuum after prune skipped: {ve}")
        return deleted_count
    finally:
        conn.close()

def delete_duplicates():
    """Delete all duplicate messages from the database and reclaim space."""
    conn = get_connection(timeout=60.0)
    try:
        c = conn.cursor()
        c.execute('DELETE FROM messages WHERE is_duplicate = 1')
        deleted_count = c.rowcount
        conn.commit()
        if deleted_count > 0:
            invalidate_database_stats_cache()
            try:
                conn.isolation_level = None
                c.execute('VACUUM')
            except Exception as ve:
                logger.warning(f"Vacuum after deleting duplicates skipped: {ve}")
        return deleted_count
    finally:
        conn.close()

def auto_prune_if_enabled():
    """Run automated data retention pruning if enabled in settings."""
    settings = get_settings()
    enabled = settings.get('auto_prune_enabled', 'true') in ('true', '1', True)
    if not enabled:
        return 0
    try:
        days = int(settings.get('auto_prune_days', 30))
    except (ValueError, TypeError):
        days = 30
    return prune_messages(days)

# In-memory stats cache with TTL to eliminate multi-second UI freezes
_stats_cache = {
    'timestamp': 0.0,
    'data': None
}

def invalidate_database_stats_cache():
    """Invalidate the cached database stats so the next request recalculates."""
    global _stats_cache
    _stats_cache['timestamp'] = 0.0
    _stats_cache['data'] = None

def _calculate_database_stats():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Höghastighets-aggregationsfråga i EN enda tabellskanning
    c.execute('''
        SELECT 
            COUNT(*),
            MIN(timestamp),
            MAX(timestamp),
            COALESCE(SUM(CASE WHEN is_protected = 1 THEN 1 ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN is_duplicate = 1 THEN 1 ELSE 0 END), 0),
            COUNT(DISTINCT address)
        FROM messages
    ''')
    row = c.fetchone()
    total_messages = row[0] if row else 0
    min_ts = row[1] if row else None
    max_ts = row[2] if row else None
    protected_count = row[3] if row else 0
    duplicate_count = row[4] if row else 0
    unique_addresses = row[5] if row else 0
    
    # 2. Blixtsnabb beräkning av alert hits i ren C-kod (ingen Python UPPER_UNICODE callback)
    c.execute('SELECT word FROM alert_words WHERE is_active = 1')
    active_words = [r[0].strip() for r in c.fetchall() if r[0] and r[0].strip()]
    alert_words_count = len(active_words)
    
    if alert_words_count == 0 or total_messages == 0:
        alert_hits = 0
    else:
        clauses = []
        params = []
        for w in active_words:
            clauses.append("m.message LIKE ?")
            params.append(f"%{w}%")
            w_lower = w.lower()
            w_upper = w.upper()
            if w_lower != w:
                clauses.append("m.message LIKE ?")
                params.append(f"%{w_lower}%")
            if w_upper != w and w_upper != w_lower:
                clauses.append("m.message LIKE ?")
                params.append(f"%{w_upper}%")
        where_sql = " OR ".join(clauses)
        c.execute(f"SELECT COUNT(*) FROM messages m WHERE {where_sql}", params)
        alert_hits = c.fetchone()[0]
    
    # 3. Antal alias
    c.execute('SELECT COUNT(*) FROM aliases')
    aliases_count = c.fetchone()[0]
    
    conn.close()
    
    # 4. Databasstorlek på disk
    db_size_bytes = 0
    if os.path.exists(DB_PATH):
        try:
            db_size_bytes = os.path.getsize(DB_PATH)
        except OSError:
            pass
            
    def format_size(bytes_size):
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.2f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"
            
    # Fetch auto-prune retention settings and save_duplicates
    settings = get_settings()
    auto_prune_enabled = settings.get('auto_prune_enabled', 'true') in ('true', '1', True)
    save_duplicates = settings.get('save_duplicates', 'true') in ('true', '1', True)
    try:
        auto_prune_days = int(settings.get('auto_prune_days', 30))
    except (ValueError, TypeError):
        auto_prune_days = 30
        
    return {
        'total_messages': total_messages,
        'alert_hits': alert_hits,
        'oldest_timestamp': min_ts,
        'newest_timestamp': max_ts,
        'protected_count': protected_count,
        'duplicate_count': duplicate_count,
        'unique_addresses': unique_addresses,
        'aliases_count': aliases_count,
        'alert_words_count': alert_words_count,
        'db_size_bytes': db_size_bytes,
        'db_size_formatted': format_size(db_size_bytes),
        'auto_prune_enabled': auto_prune_enabled,
        'auto_prune_days': auto_prune_days,
        'save_duplicates': save_duplicates
    }

def get_database_stats(force=False):
    """Retrieve comprehensive statistics about the database with in-memory TTL caching and retry on lock."""
    global _stats_cache
    now = time.time()
    
    # Om cachen är yngre än 15 sekunder och ingen forcerad uppdatering begärs: svara direkt (0 ms)
    if not force and _stats_cache['data'] is not None and (now - _stats_cache['timestamp']) < 15.0:
        return _stats_cache['data']

    for attempt in range(3):
        try:
            stats = _calculate_database_stats()
            _stats_cache['timestamp'] = now
            _stats_cache['data'] = stats
            return stats
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < 2:
                time.sleep(0.15 * (attempt + 1))
                continue
            raise

