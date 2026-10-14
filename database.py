import sqlite3
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'messages.db')

def get_connection():
    """Create a sqlite3 connection with Unicode-aware helper functions."""
    conn = sqlite3.connect(DB_PATH)
    conn.create_function("UPPER_UNICODE", 1, lambda s: (s or '').upper())
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
        'sonde_db_interval': '5'
    }

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
        ('last_timestamp', 'TEXT DEFAULT ""')
    ]:
        try:
            c.execute(f'ALTER TABLE messages ADD COLUMN {col} {type_info}')
        except sqlite3.OperationalError:
            pass # Column might already exist
    
    # Create indexes for high-speed queries on large datasets
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_id_desc ON messages(id DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_address ON messages(address)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')

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
    # Rensa automatiskt bort eventuella vanliga RDS-meddelanden (t.ex. låttexter från kommersiella FM-stationer)
    try:
        c.execute("DELETE FROM messages WHERE bitrate = 'RDS-PS' OR address LIKE 'RDS-%'")
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

def save_message(address, message, alias='', function_code=0, bitrate='', frequency='', is_duplicate=False, is_protected=False, repeat_count=1, last_timestamp=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    if last_timestamp is None:
        last_timestamp = timestamp
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE messages SET is_protected = ? WHERE id = ?', (1 if protected else 0, msg_id))
    conn.commit()
    conn.close()

def delete_message(msg_id):
    """Delete a specific message by ID."""
    conn = sqlite3.connect(DB_PATH)
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

def get_recent_messages(limit=None, before_id=None, search=None, alerts_only=False, exclude_duplicates=False):
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
                AND (
                    m.message LIKE '%' || aw.word || '%'
                    OR UPPER_UNICODE(m.message) LIKE '%' || UPPER_UNICODE(aw.word) || '%'
                )
            )
        ''')

    if before_id:
        where_clauses.append('m.id < ?')
        params.append(before_id)
        
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
            
        messages.append(msg)
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
    """Scan a message for active alert words and return the first match (word, color) or None."""
    alerts = get_alert_words()
    # Sort by length descending to match longest word first (standard practice)
    alerts.sort(key=lambda x: len(x['word']), reverse=True)
    
    msg_upper = message.upper()
    for alert in alerts:
        if not alert['is_active']:
            continue
        if alert['word'].upper() in msg_upper:
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
    """Retrieve all settings as a dictionary."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT key, value FROM settings')
    rows = c.fetchall()
    conn.close()
    
    settings = {}
    for key, value in rows:
        settings[key] = value
    return settings

def update_setting(key, value):
    """Update a specific setting."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE settings SET value = ? WHERE key = ?', (str(value), key))
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
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute('DELETE FROM messages')
        conn.commit()
        conn.isolation_level = None
        c.execute('VACUUM')
    finally:
        conn.close()

def prune_messages(days):
    """Delete messages older than X days, except protected ones."""
    conn = sqlite3.connect(DB_PATH)
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
            conn.isolation_level = None
            c.execute('VACUUM')
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

def get_database_stats():
    """Retrieve comprehensive statistics about the database and retention."""
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Total message count
    c.execute('SELECT COUNT(*) FROM messages')
    total_messages = c.fetchone()[0]
    
    # 2. Oldest and newest timestamps
    c.execute('SELECT MIN(timestamp), MAX(timestamp) FROM messages')
    min_ts, max_ts = c.fetchone()
    
    # 3. Protected / locked messages
    c.execute('SELECT COUNT(*) FROM messages WHERE is_protected = 1')
    protected_count = c.fetchone()[0]
    
    # 4. Duplicate messages
    c.execute('SELECT COUNT(*) FROM messages WHERE is_duplicate = 1')
    duplicate_count = c.fetchone()[0]
    
    # 5. Alert hits (messages matching active alert_words)
    c.execute('''
        SELECT COUNT(*) FROM messages m
        WHERE EXISTS (
            SELECT 1 FROM alert_words aw
            WHERE aw.is_active = 1
            AND (
                m.message LIKE '%' || aw.word || '%'
                OR UPPER_UNICODE(m.message) LIKE '%' || UPPER_UNICODE(aw.word) || '%'
            )
        )
    ''')
    alert_hits = c.fetchone()[0]
    
    # 6. Unique CapCodes / addresses
    c.execute('SELECT COUNT(DISTINCT address) FROM messages')
    unique_addresses = c.fetchone()[0]
    
    # 7. Total aliases count
    c.execute('SELECT COUNT(*) FROM aliases')
    aliases_count = c.fetchone()[0]
    
    # 8. Active alert words count
    c.execute('SELECT COUNT(*) FROM alert_words WHERE is_active = 1')
    alert_words_count = c.fetchone()[0]
    
    conn.close()
    
    # 9. Database file size on disk
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
            
    # Fetch auto-prune retention settings
    settings = get_settings()
    auto_prune_enabled = settings.get('auto_prune_enabled', 'true') in ('true', '1', True)
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
        'auto_prune_days': auto_prune_days
    }

