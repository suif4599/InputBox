import sys
import os
import signal
from PyQt6.QtWidgets import QSystemTrayIcon
from core import *


def main():
    app = TrayInputApp(sys.argv)
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down")
        app.quit_app()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.error("System tray not available")
        return 1
    
    logger.info("Application started successfully")
    return app.exec()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
