import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'messages.db')

def get_default_settings():
    return {
        'frequency': '161.43M',
        'gain': '35',
        'device_serial': '00000102',
        'multimon_verbosity': '1',
        'multimon_charset': 'SE',
        'multimon_format': 'auto',
        'message_font': 'JetBrains Mono',
        'message_font_size': '1.0',
        'sample_rate': '22050',
        'resample_rate': '22050',
        'enable_dc_removal': 'true',
        'ppm_error': '0',
        'enable_deemp': 'true'
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
            frequency TEXT DEFAULT ''
        )
    ''')
    
    # Try adding columns to existing messages table
    for col, type_info in [('alias', 'TEXT DEFAULT ""'), ('function_code', 'INTEGER DEFAULT 0'), ('bitrate', 'TEXT DEFAULT ""'), ('frequency', 'TEXT DEFAULT ""')]:
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
    
    # Initialize default settings if they don't exist
    defaults = get_default_settings()
    
    for key, val in defaults.items():
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))
        
    conn.commit()
    conn.close()

def save_message(address, message, alias='', function_code=0, bitrate='', frequency=''):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute('INSERT INTO messages (timestamp, address, message, alias, function_code, bitrate, frequency) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (timestamp, address, message, alias, function_code, bitrate, frequency))
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id, timestamp

def get_recent_messages(limit=100):
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
            WHERE a.is_hidden IS NULL OR a.is_hidden = 0
            ORDER BY m.id DESC LIMIT ?
        '''
    else:
        query = 'SELECT * FROM messages ORDER BY id DESC LIMIT ?'
        
    c.execute(query, (limit,))
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
