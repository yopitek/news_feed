"""
Structured logging utilities.
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pytz

TAIPEI_TZ = pytz.timezone('Asia/Taipei')


class JSONFormatter(logging.Formatter):
    """Format log records as JSON Lines."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'ts': datetime.now(TAIPEI_TZ).isoformat(),
            'level': record.levelname,
            'module': record.name,
            'msg': record.getMessage()
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


class RunLogger:
    """Logger for run-specific structured events."""
    
    def __init__(self, log_file: Union[str, Path]):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, event: str, data: Optional[dict] = None):
        """
        Log a structured event.
        
        Args:
            event: Event name
            data: Event data dictionary
        """
        entry = {
            'ts': datetime.now(TAIPEI_TZ).isoformat(),
            'event': event
        }
        
        if data:
            entry['data'] = data
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def setup_logging(
    log_file: Optional[Union[str, Path]] = None,
    debug: bool = False
):
    """
    Setup logging configuration.
    
    Args:
        log_file: Optional path to JSON Lines log file
        debug: Enable debug level logging
    """
    level = logging.DEBUG if debug else logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File handler (JSON Lines)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('feedparser').setLevel(logging.WARNING)
