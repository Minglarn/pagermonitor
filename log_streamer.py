import logging
import sys
import threading
import time
from collections import deque
from datetime import datetime
from queue import Queue, Full

# Thread-local storage to detect and prevent duplicate captures between logging and stdout tee
_tls = threading.local()

class LogManager:
    """Central log manager that keeps an in-memory ring buffer of logs

    and broadcasts new log entries to connected SSE clients.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LogManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, max_history=2500):
        if self._initialized:
            return
        self.max_history = max_history
        self.logs = deque(maxlen=max_history)
        self.subscribers = []
        self._seq_id = 0
        self.lock = threading.Lock()
        self._initialized = True

    def add_log(self, level, name, message, raw=None):
        now = datetime.now()
        timestamp_full = now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        time_short = now.strftime('%H:%M:%S')

        lvl = (level or 'INFO').upper()
        clean_name = name or 'root'
        clean_msg = str(message)

        if not raw:
            raw = f"{timestamp_full} - {clean_name} - {lvl} - {clean_msg}"

        with self.lock:
            self._seq_id += 1
            entry = {
                'id': self._seq_id,
                'timestamp': timestamp_full,
                'time': time_short,
                'level': lvl,
                'name': clean_name,
                'message': clean_msg,
                'raw': raw
            }
            self.logs.append(entry)

            # Broadcast to connected queues
            dead_subs = []
            for q in self.subscribers:
                try:
                    q.put_nowait(entry)
                except Full:
                    # Drop oldest if queue full to avoid blocking
                    try:
                        q.get_nowait()
                        q.put_nowait(entry)
                    except Exception:
                        dead_subs.append(q)
                except Exception:
                    dead_subs.append(q)

            for d in dead_subs:
                if d in self.subscribers:
                    self.subscribers.remove(d)

        return entry

    def get_history(self, limit=500, min_level=None, search=None):
        with self.lock:
            all_logs = list(self.logs)

        if search:
            search_lower = search.lower()
            all_logs = [l for l in all_logs if search_lower in l['raw'].lower()]

        if min_level and min_level.upper() != 'ALL':
            lvl_upper = min_level.upper()
            if lvl_upper == 'DECODED':
                all_logs = [l for l in all_logs if 'DECODED ->' in l['raw']]
            else:
                all_logs = [l for l in all_logs if l['level'] == lvl_upper]

        if limit and limit > 0:
            return all_logs[-limit:]
        return all_logs

    def subscribe(self):
        q = Queue(maxsize=300)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def clear(self):
        with self.lock:
            self.logs.clear()


class MemoryLogHandler(logging.Handler):
    """Logging handler that captures Python log records and routes them to LogManager."""
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        # Standard formatter matching Docker logs
        self.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        try:
            _tls.in_logging = True
            raw_text = self.format(record)
            self.manager.add_log(
                level=record.levelname,
                name=record.name,
                message=record.getMessage(),
                raw=raw_text
            )
        except Exception:
            self.handleError(record)
        finally:
            _tls.in_logging = False


class StdoutTee:
    """Tee wrapper for stdout / stderr to capture raw print() and C-level subprocess prints

    without interfering with Docker's native stdout.
    """
    def __init__(self, original_stream, manager, stream_name='STDOUT'):
        self.original_stream = original_stream
        self.manager = manager
        self.stream_name = stream_name
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, data):
        # Always forward directly to original Docker stream immediately
        try:
            self.original_stream.write(data)
            self.original_stream.flush()
        except Exception:
            pass

        # If data is generated by our logging handler, skip to prevent double logging
        if getattr(_tls, 'in_logging', False):
            return

        # Buffer lines to catch complete log lines from print()
        with self._lock:
            self._buffer += data
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                line = line.strip("\r")
                if line:
                    level = 'ERROR' if self.stream_name == 'STDERR' else 'INFO'
                    self.manager.add_log(
                        level=level,
                        name=f'sys.{self.stream_name.lower()}',
                        message=line,
                        raw=line
                    )

    def flush(self):
        try:
            self.original_stream.flush()
        except Exception:
            pass

    def fileno(self):
        return self.original_stream.fileno()

    def isatty(self):
        return getattr(self.original_stream, 'isatty', lambda: False)()


# Global instance
log_manager = LogManager()

def setup_log_capture():
    """Initializes the log capture system: attaches handler to root logger and wraps stdout/stderr."""
    # 1. Attach handler to root logger
    root_logger = logging.getLogger()
    
    # Check if already added
    for h in root_logger.handlers:
        if isinstance(h, MemoryLogHandler):
            return log_manager

    mem_handler = MemoryLogHandler(log_manager)
    mem_handler.setLevel(logging.INFO)
    root_logger.addHandler(mem_handler)

    # 2. Hook stdout and stderr
    if not isinstance(sys.stdout, StdoutTee):
        sys.stdout = StdoutTee(sys.stdout, log_manager, 'STDOUT')
    if not isinstance(sys.stderr, StdoutTee):
        sys.stderr = StdoutTee(sys.stderr, log_manager, 'STDERR')

    return log_manager
