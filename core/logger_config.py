"""
Centralized logging configuration for the input-box application.
"""
import os
import logging
import inspect
from logging.handlers import RotatingFileHandler


def setup_logging(log_file_path: str, log_level: int = logging.WARNING):
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    file_handler = RotatingFileHandler(
        log_file_path, 
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    return root_logger


class EnhancedLogger:
    """Enhanced logger that automatically captures file and line number"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _log_with_location(self, level, msg, *args, **kwargs):
        """Internal method to log with automatic file/line detection"""
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back.f_back if frame and frame.f_back else None
            if caller_frame:
                filename = os.path.basename(caller_frame.f_code.co_filename)
                lineno = caller_frame.f_lineno
                
                record = self.logger.makeRecord(
                    self.logger.name, level, caller_frame.f_code.co_filename, lineno,
                    msg, args, None, func=caller_frame.f_code.co_name
                )
                record.filename = filename
                self.logger.handle(record)
            else:
                self.logger.log(level, msg, *args, **kwargs)
        finally:
            del frame
    
    def debug(self, msg, *args, **kwargs):
        self._log_with_location(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        self._log_with_location(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        self._log_with_location(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        self._log_with_location(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        self._log_with_location(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg, *args, exc_info=True, **kwargs):
        self._log_with_location(logging.ERROR, msg, *args, exc_info=exc_info, **kwargs)


def get_logger(name: str) -> EnhancedLogger:
    return EnhancedLogger(name)


def clear_log_file(log_file_path: str) -> bool:
    try:
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write('')
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to clear log file: {e}")
        return False


def get_log_file_size(log_file_path: str) -> str:
    try:
        if not os.path.exists(log_file_path):
            return "0 B"
        
        size = os.path.getsize(log_file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except Exception:
        return "Unknown"


def update_log_level(log_level: int):
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setLevel(log_level)


def get_log_level_name(level: int) -> str:
    level_names = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO", 
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL"
    }
    return level_names.get(level, "UNKNOWN")


def get_log_level_from_name(name: str) -> int:
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING, 
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    return level_map.get(name.upper(), logging.WARNING)
