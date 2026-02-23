import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'messages.db')

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
        'ppm_error': '0',
        'enable_deemp': 'true',
        'multimon_input_type': 'raw',
        'garbage_filter': 'true',
        'garbage_filter_sensitivity': '50'
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
            is_duplicate INTEGER DEFAULT 0
        )
    ''')
    
    # Try adding columns to existing messages table
    for col, type_info in [('alias', 'TEXT DEFAULT ""'), ('function_code', 'INTEGER DEFAULT 0'), ('bitrate', 'TEXT DEFAULT ""'), ('frequency', 'TEXT DEFAULT ""'), ('is_duplicate', 'INTEGER DEFAULT 0')]:
        try:
            c.execute(f'ALTER TABLE messages ADD COLUMN {col} {type_info}')
        except sqlite3.OperationalError:
            pass # Column might already exist
    
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
            multimon_verbosity TEXT DEFAULT '2',
            multimon_charset TEXT DEFAULT 'SE',
            multimon_format TEXT DEFAULT 'auto',
            multimon_input_type TEXT DEFAULT 'raw',
            enabled INTEGER DEFAULT 1
        )
    ''')
    
    # Initialize default settings if they don't exist
    defaults = get_default_settings()
    for key, val in defaults.items():
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))

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
                multimon_verbosity, multimon_charset, multimon_format, 
                multimon_input_type, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

def save_message(address, message, alias='', function_code=0, bitrate='', frequency='', is_duplicate=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute('INSERT INTO messages (timestamp, address, message, alias, function_code, bitrate, frequency, is_duplicate) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
              (timestamp, address, message, alias, function_code, bitrate, frequency, 1 if is_duplicate else 0))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id, timestamp

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
            is_duplicate INTEGER DEFAULT 0
        )
    ''')
    
    # 2. Copy data ordered by timestamp (or old id)
    c.execute('''
        INSERT INTO messages_new (timestamp, address, message, alias, function_code, bitrate, frequency, is_duplicate)
        SELECT timestamp, address, message, alias, function_code, bitrate, frequency, is_duplicate
        FROM messages ORDER BY timestamp ASC
    ''')
    
    # 3. Swap tables
    c.execute('DROP TABLE messages')
    c.execute('ALTER TABLE messages_new RENAME TO messages')
    
    if not already_open_conn:
        conn.commit()
        conn.close()

def get_recent_messages(limit=100, before_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if we have the is_hidden column in aliases
    c.execute('PRAGMA table_info(aliases)')
    columns = [col[1] for col in c.fetchall()]
    has_hidden = 'is_hidden' in columns
    
    if has_hidden:
        # Join with aliases table to filter out hidden messages
        query = '''
            SELECT m.* FROM messages m
            LEFT JOIN aliases a ON m.address = a.address
            WHERE (a.is_hidden IS NULL OR a.is_hidden = 0)
        '''
        params = []
        if before_id:
            query += ' AND m.id < ?'
            params.append(before_id)
        query += ' ORDER BY m.id DESC LIMIT ?'
        params.append(limit)
    else:
        query = 'SELECT * FROM messages'
        params = []
        if before_id:
            query += ' WHERE id < ?'
            params.append(before_id)
        query += ' ORDER BY id DESC LIMIT ?'
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

    conn.close()
    
    messages = []
    for row in rows:
        msg = {
            'id': row[id_idx],
            'timestamp': row[ts_idx],
            'address': row[addr_idx],
            'message': row[msg_idx],
            'alias': row[alias_idx] if alias_idx != -1 else ''
        }
        # Add metadata if exists
        if 'function_code' in col_names:
            msg['function_code'] = row[col_names.index('function_code')]
        if 'bitrate' in col_names:
            msg['bitrate'] = row[col_names.index('bitrate')]
        if 'frequency' in col_names:
            msg['frequency'] = row[col_names.index('frequency')]
        if 'is_duplicate' in col_names:
            msg['is_duplicate'] = bool(row[col_names.index('is_duplicate')])
            
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
    name = data.get('name', 'Ny mottagare')
    freq = data.get('frequency', '169.8M')
    gain = data.get('gain', 'auto')
    serial = data.get('device_serial', '')
    ppm = data.get('ppm_error', '0')
    sample_rate = data.get('sample_rate', '22050')
    resample_rate = data.get('resample_rate', '22050')
    dc = data.get('enable_dc_removal', 'true')
    deemp = data.get('enable_deemp', 'true')
    verb = data.get('multimon_verbosity', '1')
    charset = data.get('multimon_charset', 'SE')
    fmt = data.get('multimon_format', 'auto')
    inp = data.get('multimon_input_type', 'raw')
    enabled = data.get('enabled', 1)

    if instance_id:
        c.execute('''
            UPDATE sdr_instances SET 
                name=?, frequency=?, gain=?, device_serial=?, ppm_error=?,
                sample_rate=?, resample_rate=?, enable_dc_removal=?, enable_deemp=?,
                multimon_verbosity=?, multimon_charset=?, multimon_format=?,
                multimon_input_type=?, enabled=?
            WHERE id=?
        ''', (name, freq, gain, serial, ppm, sample_rate, resample_rate, dc, deemp, verb, charset, fmt, inp, enabled, instance_id))
    else:
        c.execute('''
            INSERT INTO sdr_instances (
                name, frequency, gain, device_serial, ppm_error,
                sample_rate, resample_rate, enable_dc_removal, enable_deemp,
                multimon_verbosity, multimon_charset, multimon_format,
                multimon_input_type, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, freq, gain, serial, ppm, sample_rate, resample_rate, dc, deemp, verb, charset, fmt, inp, 1))
        
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
