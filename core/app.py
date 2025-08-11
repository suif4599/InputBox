import os
import threading
import asyncio
import subprocess
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QVBoxLayout, QDialog, QPushButton, QTextBrowser
                             
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QTimer
from .hotkey_manager import create_hotkey_manager, HotkeyManager
from .tools import *
from .settings import SettingsDialog
from .input import InputDialog



class TrayInputApp(QApplication):
    show_input_signal = pyqtSignal()
    
    def __init__(self, argv):
        super().__init__(argv)
        
        logger.info("Initializing TrayInputApp")

        if not is_running_under_service():
            try:
                subprocess.run(['systemctl', '--user', 'stop', "input-box.service"], check=True)
            except subprocess.CalledProcessError as e:
                pass
        
        config_path = os.path.join(ROOT, "input-box.config")
        self.settings = QSettings(config_path, QSettings.Format.IniFormat)
        
        saved_log_level = self.settings.value("log_level", "WARNING", str)
        level = get_log_level_from_name(saved_log_level)
        update_log_level(level)
        logger.info(f"Applied saved log level: {saved_log_level}")
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.create_icon())
        self.tray_icon.setToolTip("Quick Input Tool")
        
        menu = QMenu()
        menu.addAction("Show Input", self.show_input)
        menu.addAction("Settings", self.show_settings)
        menu.addAction("Help", self.show_help)
        menu.addSeparator()
        menu.addAction("Quit", self.quit_app)

        self.tray_icon.setContextMenu(menu)
        self.input_dialog = InputDialog()
        self.show_input_signal.connect(self.show_input)
        
        logger.info("Creating hotkey manager")
        self.hotkey_manager: HotkeyManager = create_hotkey_manager('auto')
        self.hotkey_loop = None
        self.hotkey_thread = None
        
        self.setup_global_hotkey()
        self.tray_icon.show()
        self.setQuitOnLastWindowClosed(False)
        
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: None)
        self.timer.start(200)
        
        logger.info("TrayInputApp initialization completed")
    
    def show_settings(self):
        logger.info("Opening settings dialog")
        dialog = SettingsDialog(self)
        dialog.parent_app = self
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("Settings accepted, restarting hotkey")
            self.stop_hotkey_temporarily()
            import time
            time.sleep(0.1)
            self.setup_global_hotkey()
        else:
            logger.info("Settings dialog cancelled")
    
    def _run_async_in_thread(self, coro_func, *args):
        """Run an async function in a dedicated thread with its own event loop."""
        def run_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(coro_func(*args))
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error in async thread: {e}")
        
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        return thread
    
    def show_help(self):
        # Show help dialog with content from help.md file
        help_file_path = os.path.join(os.path.dirname(__file__), "help.md")
        help_content = "Help file not found."
        
        try:
            if os.path.exists(help_file_path):
                with open(help_file_path, 'r', encoding='utf-8') as f:
                    help_content = f.read()
        except Exception as e:
            help_content = f"Error reading help file: {e}"
        
        help_dialog = QDialog()
        help_dialog.setWindowTitle("Help")
        help_dialog.setModal(True)
        help_dialog.resize(600, 400)
        
        layout = QVBoxLayout()
        text_browser = QTextBrowser()
        text_browser.setMarkdown(help_content)
        layout.addWidget(text_browser)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(help_dialog.accept)
        layout.addWidget(close_btn)
        help_dialog.setLayout(layout)
        help_dialog.exec()
    
    def stop_hotkey_temporarily(self):
        """Stop hotkey temporarily (called during settings editing)."""
        if self.hotkey_loop and not self.hotkey_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(self.hotkey_manager.stop(), self.hotkey_loop)
            try:
                future.result(timeout=2.0)
            except Exception as e:
                logger.error(f"Error stopping hotkey: {e}")
        
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            self.hotkey_thread.join(timeout=2.0)
        self.hotkey_manager = create_hotkey_manager('auto')
    
    def restart_hotkey_temporarily(self):
        """Restart hotkey (called after settings editing)."""
        self.setup_global_hotkey()
    
    def setup_global_hotkey(self):
        """Setup global hotkey using dedicated event loop thread."""
        if self.hotkey_loop and not self.hotkey_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(self.hotkey_manager.stop(), self.hotkey_loop)
            try:
                future.result(timeout=2.0)
            except Exception as e:
                logger.error(f"Error stopping existing hotkey: {e}")
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            self.hotkey_thread.join(timeout=2.0)
        if not self.settings.value("enable_hotkey", True, bool):
            return
        
        def run_hotkey_loop():
            """Run the hotkey manager in its own event loop."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.hotkey_loop = loop
            
            async def setup_and_run():
                try:
                    hotkey_sequence = self.settings.value("hotkey", "Ctrl+Q", str)
                    
                    def on_hotkey():
                        self.show_input_signal.emit()
                    
                    success = await self.hotkey_manager.register_hotkey(hotkey_sequence, on_hotkey)
                    if success:
                        await self.hotkey_manager.start()
                        while self.hotkey_manager.is_active:
                            await asyncio.sleep(0.1)
                    else:
                        logger.error(f"Failed to register hotkey: {hotkey_sequence}")
                except Exception as e:
                    logger.error(f"Error in hotkey setup: {e}")
            
            try:
                loop.run_until_complete(setup_and_run())
            except Exception as e:
                logger.error(f"Error in hotkey loop: {e}")
            finally:
                loop.close()
                self.hotkey_loop = None
        
        self.hotkey_thread = threading.Thread(target=run_hotkey_loop, daemon=True)
        self.hotkey_thread.start()
        
    def create_icon(self):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(Qt.GlobalColor.blue)
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        return QIcon(pixmap)
    
    def show_input(self):
        logger.debug("Showing input dialog")
        self.input_dialog.text_edit.clear()
        self.input_dialog.show()
        self.input_dialog.raise_()
        self.input_dialog.activateWindow()
    
    def quit_app(self):
        logger.info("Shutting down application")
        if self.hotkey_loop and not self.hotkey_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(self.hotkey_manager.stop(), self.hotkey_loop)
            try:
                future.result(timeout=2.0)
            except Exception as e:
                logger.error(f"Error stopping hotkey manager: {e}")
        
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            self.hotkey_thread.join(timeout=2.0)
        
        if self.tray_icon:
            self.tray_icon.hide()
        logger.info("Application shutdown complete")
        self.quit()
