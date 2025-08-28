import os
import threading
import asyncio
import subprocess
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QVBoxLayout, QDialog, QPushButton, QTextBrowser
                             
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QTimer
from .hotkey_manager import create_hotkey_manager, HotkeyManager
from .tools import *
from .settings import SettingsDialog, load_and_validate_settings, save_settings_to_file
from .input import InputDialog

# Import plugin system
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from interface import CallbackPosition, CallbackContext
from plugins import init_plugin_manager, get_plugin_manager



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
        
        # Initialize plugin system
        plugins_dir = os.path.join(ROOT, "plugins")
        self.plugin_manager = init_plugin_manager(plugins_dir, logger)
        self.plugin_manager.load_plugins()
        
        # Create callback context for plugin initialization
        context = CallbackContext(app=self, logger=logger)
        
        # Trigger launch callbacks
        self.plugin_manager.trigger_callbacks(CallbackPosition.ON_LAUNCH, context)
        
        self.settings = load_and_validate_settings()
        saved_log_level = self.settings.value("log_level", "WARNING", str)
        level = get_log_level_from_name(saved_log_level)
        update_log_level(level)
        logger.info(f"Applied saved log level: {saved_log_level}")
        
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.create_tray_icon())
        self.tray_icon.setToolTip("Quick Input Tool")
        
        menu = QMenu()
        menu.addAction("Show Input", self.show_input)
        menu.addAction("Settings", self.show_settings)
        menu.addAction("Plugins", self.show_plugin_manager)
        menu.addAction("Help", self.show_help)
        menu.addSeparator()
        menu.addAction("Quit", self.quit_app)

        self.tray_icon.setContextMenu(menu)
        self.input_dialog = InputDialog(self)  # Pass app reference
        self.show_input_signal.connect(self.show_input)
        
        logger.info("Creating hotkey manager")
        preferred_manager = self.settings.value("hotkey_manager", "auto", str)
        self.hotkey_manager: HotkeyManager = create_hotkey_manager(preferred_manager)
        self.hotkey_loop = None
        self.hotkey_thread = None
        
        self.setup_global_hotkey()
        self.tray_icon.show()
        self.setQuitOnLastWindowClosed(False)
        
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: None)
        self.timer.start(200)
        
        # Initialize plugins after everything is set up
        self.plugin_manager.initialize_plugins(context)
        
        logger.info("TrayInputApp initialization completed")
    
    def show_settings(self):
        logger.info("Opening settings dialog")
        
        # Trigger settings show callback
        context = CallbackContext(app=self, logger=logger)
        self.plugin_manager.trigger_callbacks(CallbackPosition.ON_SETTINGS_SHOW, context)
        
        dialog = SettingsDialog(self)
        dialog.parent_app = self
        icon_path = os.path.join(ROOT, "icon.png")
        if os.path.exists(icon_path):
            try:
                icon = QIcon(icon_path)
                if not icon.isNull():
                    dialog.setWindowIcon(icon)
            except Exception:
                pass
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("Settings accepted, restarting hotkey")
            self.stop_hotkey_temporarily()
            import time
            time.sleep(0.1)
            self.setup_global_hotkey()
        else:
            logger.info("Settings dialog cancelled")
            
        # Trigger settings hide callback
        self.plugin_manager.trigger_callbacks(CallbackPosition.ON_SETTINGS_HIDE, context)
    
    def show_plugin_manager(self):
        """Show the plugin manager dialog."""
        logger.info("Opening plugin manager dialog")
        
        from .plugin_manager_dialog import PluginManagerDialog
        dialog = PluginManagerDialog(self)
        
        # Set icon
        icon_path = os.path.join(ROOT, "icon.png")
        if os.path.exists(icon_path):
            try:
                icon = QIcon(icon_path)
                if not icon.isNull():
                    dialog.setWindowIcon(icon)
            except Exception:
                pass
        
        dialog.exec()
        logger.info("Plugin manager dialog closed")
    
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
        help_file_path = os.path.join(ROOT, "help.md")
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
        icon_path = os.path.join(ROOT, "icon.png")
        if os.path.exists(icon_path):
            try:
                icon = QIcon(icon_path)
                if not icon.isNull():
                    help_dialog.setWindowIcon(icon)
            except Exception:
                pass
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
        preferred_manager = self.settings.value("hotkey_manager", "auto", str)
        self.hotkey_manager = create_hotkey_manager(preferred_manager)
    
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
                        # Trigger hotkey callback
                        context = CallbackContext(app=self, logger=logger)
                        self.plugin_manager.trigger_callbacks(CallbackPosition.ON_HOTKEY_TRIGGERED, context)
                        
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
        
    def create_tray_icon(self):
        """Create tray icon, preferring ROOT/icon.png, falling back to drawn blue circle."""
        icon_path = os.path.join(ROOT, "icon.png")
        if os.path.exists(icon_path):
            try:
                icon = QIcon(icon_path)
                if not icon.isNull():
                    logger.debug(f"Using icon from {icon_path}")
                    return icon
                else:
                    logger.warning(f"Icon file exists but failed to load: {icon_path}")
            except Exception as e:
                logger.warning(f"Error loading icon from {icon_path}: {e}")
        logger.debug("Using fallback drawn tray icon")
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(Qt.GlobalColor.blue)
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        return QIcon(pixmap)
    
    def show_input(self):
        logger.debug("Showing input dialog")
        
        # Trigger input box show callback
        context = CallbackContext(app=self, logger=logger)
        self.plugin_manager.trigger_callbacks(CallbackPosition.ON_INPUT_BOX_SHOW, context)
        
        self.input_dialog.ensure_focus()
    
    def quit_app(self):
        logger.info("Shutting down application")
        
        # Trigger exit callbacks
        context = CallbackContext(app=self, logger=logger)
        self.plugin_manager.trigger_callbacks(CallbackPosition.ON_EXIT, context)
        
        if hasattr(self.input_dialog, '_cached_root_password'):
            self.input_dialog._cached_root_password = None
        try:
            settings_dict = {
                "enable_hotkey": self.settings.value("enable_hotkey", True, bool),
                "hotkey": self.settings.value("hotkey", "Ctrl+Q", str),
                "hotkey_manager": self.settings.value("hotkey_manager", "auto", str),
                "auto_paste": self.settings.value("auto_paste", True, bool),
                "preserve_clipboard": self.settings.value("preserve_clipboard", True, bool),
                "log_level": self.settings.value("log_level", "WARNING", str),
                "auto_file_link": self.settings.value("auto_file_link", False, bool),
                "target_directory": self.settings.value("target_directory", ROOT, str),
                "use_symlink": self.settings.value("use_symlink", False, bool),
                "auto_startup": self.settings.value("auto_startup", True, bool),
                "active_dismissal_behavior": self.settings.value("active_dismissal_behavior", "content_and_cursor", str),
                "passive_dismissal_behavior": self.settings.value("passive_dismissal_behavior", "follow_active", str)
            }
            save_settings_to_file(settings_dict)
        except Exception as e:
            logger.error(f"Failed to save settings on exit: {e}")
        
        if self.hotkey_loop and not self.hotkey_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(self.hotkey_manager.stop(), self.hotkey_loop)
            try:
                future.result(timeout=2.0)
            except Exception as e:
                logger.error(f"Error stopping hotkey manager: {e}")
        
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            self.hotkey_thread.join(timeout=2.0)
        
        # Shutdown plugins
        self.plugin_manager.shutdown_plugins(context)
        
        if self.tray_icon:
            self.tray_icon.hide()
        logger.info("Application shutdown complete")
        self.quit()
