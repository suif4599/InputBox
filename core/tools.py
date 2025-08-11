import os
import logging
import inspect
from .logger_config import *

__frame = inspect.currentframe()
while __frame and __frame.f_back and __frame.f_globals["__name__"] != "__main__":
    __frame = __frame.f_back
if not __frame or __frame.f_globals["__name__"] != "__main__":
    raise RuntimeError("tools.py should only be run as part of the main application")
ROOT = os.path.dirname(os.path.abspath(__frame.f_globals["__file__"]))


log_file_path = os.path.join(ROOT, "input-box.log")
setup_logging(log_file_path, logging.WARNING)
logger = get_logger(__name__)


def is_running_under_service() -> bool:
    """Check if the current process is running under systemd service."""
    try:
        # Check if parent process is systemd
        try:
            import psutil
        except ImportError:
            logger.debug("psutil not available, skipping parent process check")
            psutil = None
        if psutil:
            try:
                current_process = psutil.Process()
                parent = current_process.parent()
                tree = [current_process.name()]
                while parent:
                    tree.append(parent.name())
                    parent = parent.parent()
                if not "conda" in tree:
                    return False
                idx = tree.index("conda")
                if tree[idx + 1] == "systemd":
                    logger.debug("Detected running under systemd (parent process check)")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                logger.debug(f"Error in parent process check: {e}")
        
        logger.debug("Not running under systemd service")
        return False
        
    except Exception as e:
        logger.warning(f"Error checking service status: {e}")
        return False
    
