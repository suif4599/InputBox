import sys
import os
import subprocess
from PyQt6.QtWidgets import (QVBoxLayout, QDialog, QCheckBox, QLabel, QHBoxLayout,
                             QPushButton, QKeySequenceEdit, QMessageBox, QComboBox,
                             QFileDialog, QFrame)
from PyQt6.QtGui import QKeySequence
from PyQt6.QtCore import QSettings

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .app import TrayInputApp

from .tools import *
from .hotkey_manager import get_available_managers, get_auto_manager_name, get_manager_display_name


def load_and_validate_settings():
    """Load settings from file and validate/filter conflicting options."""
    config_path = os.path.join(ROOT, "input-box.config")
    settings = QSettings(config_path, QSettings.Format.IniFormat)
    
    # Flag to track if we need to save after validation
    needs_save = False
    
    # Validate auto file linking dependency on auto paste
    auto_file_link = settings.value("auto_file_link", False, bool)
    auto_paste = settings.value("auto_paste", True, bool)
    
    if auto_file_link and not auto_paste:
        logger.warning("Auto file linking requires auto paste - disabling auto file linking")
        settings.setValue("auto_file_link", False)
        needs_save = True
    
    # Validate target directory exists
    target_directory = settings.value("target_directory", ROOT, str)
    if not os.path.exists(target_directory):
        logger.warning(f"Target directory {target_directory} does not exist - falling back to ROOT")
        settings.setValue("target_directory", ROOT)
        needs_save = True
    
    # Save if validation made changes
    if needs_save:
        settings.sync()
        logger.info("Settings validated and conflicts resolved")
    
    return settings


def save_settings_to_file(settings_dict):
    """Save settings dictionary to file."""
    config_path = os.path.join(ROOT, "input-box.config")
    settings = QSettings(config_path, QSettings.Format.IniFormat)
    
    for key, value in settings_dict.items():
        settings.setValue(key, value)
    
    settings.sync()
    logger.info("Settings saved to file")


class SettingsDialog(QDialog):
    def __init__(self, parent: "TrayInputApp"):
        super().__init__(None) # Must set to None
        self.__my_parent = parent
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 200)
        
        self.parent_app = parent
        # Load and validate settings at initialization
        self.settings = load_and_validate_settings()
        
        layout = QVBoxLayout()
        self.enable_hotkey_cb = QCheckBox("Enable hotkey activation")
        self.enable_hotkey_cb.setChecked(self.settings.value("enable_hotkey", True, bool))
        layout.addWidget(self.enable_hotkey_cb)
        
        # Hotkey manager selection
        hotkey_manager_layout = QHBoxLayout()
        hotkey_manager_layout.addWidget(QLabel("Hotkey Manager:"))
        self.hotkey_manager_combo = QComboBox()
        
        # Get available managers and populate combo box
        available_managers = get_available_managers()
        auto_manager = get_auto_manager_name()
        auto_display_name = get_manager_display_name(auto_manager)
        
        # Add auto option with current manager info
        self.hotkey_manager_combo.addItem(f"Auto ({auto_display_name})", "auto")
        
        # Add individual managers
        for manager_key in available_managers.keys():
            display_name = get_manager_display_name(manager_key)
            self.hotkey_manager_combo.addItem(display_name, manager_key)
        
        # Set current selection
        current_manager = self.settings.value("hotkey_manager", "auto", str)
        current_index = self.hotkey_manager_combo.findData(current_manager)
        if current_index >= 0:
            self.hotkey_manager_combo.setCurrentIndex(current_index)
        
        hotkey_manager_layout.addWidget(self.hotkey_manager_combo)
        layout.addLayout(hotkey_manager_layout)
        
        hotkey_layout = QHBoxLayout()
        hotkey_layout.addWidget(QLabel("Hotkey:"))
        self.hotkey_edit = QKeySequenceEdit()
        self.hotkey_edit.setMaximumSequenceLength(1)
        default_hotkey = self.settings.value("hotkey", "Ctrl+Q", str)
        self.hotkey_edit.setKeySequence(QKeySequence(default_hotkey))
        hotkey_layout.addWidget(self.hotkey_edit)
        layout.addLayout(hotkey_layout)
        
        self.hotkey_edit.editingFinished.connect(self.on_hotkey_edit_finished)
        self.hotkey_edit.keySequenceChanged.connect(self.on_hotkey_recording_started)
        self.auto_paste_cb = QCheckBox("Enable auto paste after copying")
        self.auto_paste_cb.setChecked(self.settings.value("auto_paste", True, bool))
        layout.addWidget(self.auto_paste_cb)
        self.preserve_clipboard_cb = QCheckBox("Preserve original clipboard content")
        self.preserve_clipboard_cb.setChecked(self.settings.value("preserve_clipboard", True, bool))
        layout.addWidget(self.preserve_clipboard_cb)
        self.auto_paste_cb.toggled.connect(self.on_auto_paste_toggled)
        self.enable_hotkey_cb.toggled.connect(self.on_enable_hotkey_toggled)
        self.on_enable_hotkey_toggled(self.enable_hotkey_cb.isChecked())

        log_level_layout = QHBoxLayout()
        log_level_layout.addWidget(QLabel("Log Level:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        
        current_log_level = self.settings.value("log_level", "WARNING", str)
        current_index = self.log_level_combo.findText(current_log_level)
        if current_index >= 0:
            self.log_level_combo.setCurrentIndex(current_index)
        
        self.log_level_combo.currentTextChanged.connect(self.on_log_level_changed)
        log_level_layout.addWidget(self.log_level_combo)
        layout.addLayout(log_level_layout)

        log_layout = QHBoxLayout()
        log_size_label = QLabel(f"Log size: {get_log_file_size(log_file_path)}")
        log_layout.addWidget(log_size_label)
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(lambda: self.clear_log_file(log_size_label))
        log_layout.addWidget(clear_log_btn)
        layout.addLayout(log_layout)

        service_layout = QHBoxLayout()
        service_label = QLabel("System Service:")
        service_layout.addWidget(service_label)
        
        if is_running_under_service():
            self.service_btn = QPushButton("Restart Service")
            self.service_btn.clicked.connect(self.restart_service)
        else:
            self.service_btn = QPushButton("Register Service")
            self.service_btn.clicked.connect(self.register_service)
        
        service_layout.addWidget(self.service_btn)
        layout.addLayout(service_layout)

        # Auto-startup checkbox (always visible, but disabled when not running under service)
        self.auto_startup_cb = QCheckBox("Enable auto-startup on boot")
        self.auto_startup_cb.setChecked(self.is_service_enabled())
        
        # Enable/disable based on whether running under service
        if not is_running_under_service():
            self.auto_startup_cb.setEnabled(False)
            self.auto_startup_cb.setToolTip("This option is only available when running as a system service")
        
        layout.addWidget(self.auto_startup_cb)

        # Advanced Settings Section (at the bottom)
        self.advanced_button = QPushButton("Advanced Settings")
        self.advanced_button.setCheckable(True)
        self.advanced_button.clicked.connect(self.toggle_advanced_settings)
        layout.addWidget(self.advanced_button)
        
        # Advanced settings frame (initially hidden)
        self.advanced_frame = QFrame()
        self.advanced_frame.setFrameStyle(QFrame.Shape.Box)
        self.advanced_frame.setVisible(False)
        
        advanced_layout = QVBoxLayout()
        
        # Auto file link checkbox (depends on auto paste)
        self.auto_file_link_cb = QCheckBox("Enable automatic file linking")
        auto_file_link_enabled = self.settings.value("auto_file_link", False, bool)
        auto_paste_enabled = self.settings.value("auto_paste", True, bool)
        
        # Only enable auto file linking if auto paste is also enabled
        if auto_file_link_enabled and not auto_paste_enabled:
            auto_file_link_enabled = False
            self.settings.setValue("auto_file_link", False)
        
        self.auto_file_link_cb.setChecked(auto_file_link_enabled)
        self.auto_file_link_cb.setEnabled(auto_paste_enabled)
        self.auto_file_link_cb.toggled.connect(self.on_auto_file_link_toggled)
        
        if not auto_paste_enabled:
            self.auto_file_link_cb.setToolTip("Auto file linking requires auto paste to be enabled")
        
        advanced_layout.addWidget(self.auto_file_link_cb)
        
        # Target directory selection
        target_dir_layout = QHBoxLayout()
        target_dir_layout.addWidget(QLabel("Target directory:"))
        
        self.target_dir_button = QPushButton()
        default_target_dir = self.settings.value("target_directory", ROOT, str)
        # Ensure target directory exists, fallback to ROOT if not
        if not os.path.exists(default_target_dir):
            default_target_dir = ROOT
            self.settings.setValue("target_directory", default_target_dir)
        
        self.target_dir_button.setText(shorten_path(default_target_dir))
        self.target_dir_button.clicked.connect(self.select_target_directory)
        target_dir_layout.addWidget(self.target_dir_button)
        advanced_layout.addLayout(target_dir_layout)
        
        # Use symlink checkbox
        self.use_symlink_cb = QCheckBox("Use symbolic links instead of hard links")
        self.use_symlink_cb.setChecked(self.settings.value("use_symlink", False, bool))
        advanced_layout.addWidget(self.use_symlink_cb)
        
        # Clean up links button
        cleanup_layout = QHBoxLayout()
        cleanup_layout.addWidget(QLabel("Link Management:"))
        self.cleanup_links_btn = QPushButton("Clean Up Created Links")
        self.cleanup_links_btn.clicked.connect(self.cleanup_created_links)
        cleanup_layout.addWidget(self.cleanup_links_btn)
        advanced_layout.addLayout(cleanup_layout)
        
        # Input preservation settings
        preservation_label = QLabel("Input Preservation Settings:")
        preservation_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        advanced_layout.addWidget(preservation_label)
        
        # Active dismissal (Esc key) preservation
        active_dismissal_layout = QHBoxLayout()
        active_dismissal_layout.addWidget(QLabel("When pressing Esc:"))
        self.active_dismissal_combo = QComboBox()
        self.active_dismissal_combo.addItem("Save content and cursor position", "content_and_cursor")
        self.active_dismissal_combo.addItem("Save content only", "content_only")
        self.active_dismissal_combo.addItem("Don't save anything", "no_save")
        
        current_active_setting = self.settings.value("active_dismissal_behavior", "content_and_cursor", str)
        active_index = self.active_dismissal_combo.findData(current_active_setting)
        if active_index >= 0:
            self.active_dismissal_combo.setCurrentIndex(active_index)
        
        active_dismissal_layout.addWidget(self.active_dismissal_combo)
        advanced_layout.addLayout(active_dismissal_layout)
        
        # Passive dismissal (focus loss) preservation
        passive_dismissal_layout = QHBoxLayout()
        passive_dismissal_layout.addWidget(QLabel("When losing focus:"))
        self.passive_dismissal_combo = QComboBox()
        self.passive_dismissal_combo.addItem("Follow Esc behavior", "follow_active")
        self.passive_dismissal_combo.addItem("Save content and cursor position", "content_and_cursor")
        self.passive_dismissal_combo.addItem("Save content only", "content_only")
        self.passive_dismissal_combo.addItem("Don't save anything", "no_save")
        
        current_passive_setting = self.settings.value("passive_dismissal_behavior", "follow_active", str)
        passive_index = self.passive_dismissal_combo.findData(current_passive_setting)
        if passive_index >= 0:
            self.passive_dismissal_combo.setCurrentIndex(passive_index)
        
        passive_dismissal_layout.addWidget(self.passive_dismissal_combo)
        advanced_layout.addLayout(passive_dismissal_layout)
        
        self.advanced_frame.setLayout(advanced_layout)
        layout.addWidget(self.advanced_frame)
        
        # Initialize the state of advanced controls
        self.on_auto_file_link_toggled(self.auto_file_link_cb.isChecked())
        # Initialize auto paste state after all UI elements are created
        self.on_auto_paste_toggled(self.auto_paste_cb.isChecked())

        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self._fix_dialog_width()
    
    def _fix_dialog_width(self):
        """Calculate and fix the dialog width based on the expanded advanced settings."""
        was_visible = self.advanced_frame.isVisible()
        self.advanced_frame.setVisible(True)
        layout = self.layout()
        if layout:
            layout.activate()
        self.adjustSize()
        max_width = self.width()
        self.advanced_frame.setVisible(was_visible)
        self.setFixedWidth(max_width)
        if not was_visible:
            self.adjustSize()
    
    def on_auto_paste_toggled(self, checked):
        self.preserve_clipboard_cb.setEnabled(checked)
        if not checked:
            self.preserve_clipboard_cb.setChecked(False)
            self.auto_file_link_cb.setChecked(False)
            self.auto_file_link_cb.setEnabled(False)
            self.auto_file_link_cb.setToolTip("Auto file linking requires auto paste to be enabled")
        else:
            self.preserve_clipboard_cb.setChecked(True)
            self.auto_file_link_cb.setEnabled(True)
            self.auto_file_link_cb.setToolTip("")
        
        self.on_auto_file_link_toggled(self.auto_file_link_cb.isChecked())
    
    def on_enable_hotkey_toggled(self, checked):
        self.hotkey_edit.setEnabled(checked)
        self.hotkey_manager_combo.setEnabled(checked)
    
    def toggle_advanced_settings(self):
        """Toggle the visibility of advanced settings."""
        is_visible = self.advanced_frame.isVisible()
        self.advanced_frame.setVisible(not is_visible)
        self.advanced_button.setText("Advanced Settings" if is_visible else "Hide Advanced Settings")
        current_width = self.width()
        self.adjustSize()
        self.setFixedWidth(current_width)
    
    def on_auto_file_link_toggled(self, checked):
        """Enable/disable target directory and symlink options based on auto file link setting."""
        auto_paste_enabled = self.auto_paste_cb.isChecked()
        controls_enabled = checked and auto_paste_enabled
        
        self.target_dir_button.setEnabled(controls_enabled)
        self.use_symlink_cb.setEnabled(controls_enabled)
        self.cleanup_links_btn.setEnabled(True)
    
    def select_target_directory(self):
        """Open directory selection dialog for target directory."""
        current_dir = expand_path(self.target_dir_button.text())
        selected_dir = QFileDialog.getExistingDirectory(
            self, 
            "Select Target Directory", 
            current_dir
        )
        if selected_dir:
            self.target_dir_button.setText(shorten_path(selected_dir))
    
    def cleanup_created_links(self):
        """Open the link cleanup dialog."""
        from .input import InputDialog
        temp_dialog = InputDialog()
        temp_dialog.cleanup_created_links()

    def on_log_level_changed(self, level_name):
        """Handle log level change."""
        level = get_log_level_from_name(level_name)
        update_log_level(level)
        logger.info(f"Log level changed to: {level_name}")
    
    def clear_log_file(self, log_size_label):
        reply = QMessageBox.question(
            self, 
            "Clear Log", 
            "Are you sure you want to clear the log file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if clear_log_file(log_file_path):
                log_size_label.setText(f"Log size: {get_log_file_size(log_file_path)}")
                logger.info("Log file cleared by user")
            else:
                QMessageBox.warning(self, "Error", "Failed to clear log file.")
    
    def register_service(self):
        """Register the generated service with systemd as a user service."""
        try:
            main_py_path = os.path.join(ROOT, "main.py")

            conda_env = os.environ.get('CONDA_DEFAULT_ENV')
            conda_prefix = os.environ.get('CONDA_PREFIX')
            conda_exe = os.environ.get('CONDA_EXE')
            
            if not conda_env or not conda_prefix or not conda_exe:
                python_executable = sys.executable
                if 'conda' in python_executable or 'anaconda' in python_executable:
                    import re
                    env_match = re.search(r'envs/([^/]+)/', python_executable)
                    if env_match:
                        conda_env = env_match.group(1)
                        conda_base_match = re.search(r'(.+?)/envs/', python_executable)
                        if conda_base_match:
                            conda_base = conda_base_match.group(1)
                            conda_exe = os.path.join(conda_base, 'bin', 'conda')
                            if not os.path.exists(conda_exe):
                                conda_exe = os.path.join(conda_base, 'condabin', 'conda')
                    else:
                        base_match = re.search(r'(.+?)/bin/python', python_executable)
                        if base_match:
                            conda_base = base_match.group(1)
                            conda_exe = os.path.join(conda_base, 'bin', 'conda')
                            if not os.path.exists(conda_exe):
                                conda_exe = os.path.join(conda_base, 'condabin', 'conda')
                            conda_env = 'base'
            
            if not conda_env or not conda_exe or not os.path.exists(conda_exe):
                QMessageBox.critical(
                    self,
                    "Conda Environment Required",
                    "Conda environment not detected.\n\n"
                    "Please ensure:\n"
                    "1. You are running this program inside a conda environment\n"
                    "2. CONDA_DEFAULT_ENV and CONDA_EXE environment variables are set\n"
                    "3. Or the current Python interpreter is inside a conda environment\n\n"
                    "Service registration failed."
                )
                return
            
            user_id = os.getuid()
            
            if conda_env == 'base':
                exec_command = f"{conda_exe} run python {main_py_path}"
            else:
                exec_command = f"{conda_exe} run -n {conda_env} python {main_py_path}"

            display = os.environ.get("DISPLAY", ":0")
            session_type = os.environ.get("XDG_SESSION_TYPE", "x11")
            wayland_display = os.environ.get("WAYLAND_DISPLAY", "")

            service_content = f"""[Unit]
Description=Input Box - Quick Input Tool
After=graphical-session.target
Wants=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
Environment="DISPLAY={display}"
Environment="XDG_RUNTIME_DIR=/run/user/{user_id}"
Environment="HOME={os.path.expanduser('~')}"
Environment="XDG_SESSION_TYPE={session_type}"
Environment="WAYLAND_DISPLAY={wayland_display}"
Environment="PATH={os.environ.get('PATH', '')}"
ExecStart={exec_command}
Restart=on-failure
RestartSec=5
WorkingDirectory={ROOT}

[Install]
WantedBy=graphical-session.target
"""
            
            user_systemd_dir = os.path.expanduser("~/.config/systemd/user")
            target_path = os.path.join(user_systemd_dir, "input-box.service")
            
            if os.path.exists(target_path):
                reply = QMessageBox.question(
                    self,
                    "Service Already Exists",
                    "The service file already exists. Do you want to overwrite it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    logger.info("User chose not to overwrite existing service file.")
                    return
                try:
                    subprocess.run(['systemctl', '--user', 'stop', 'input-box.service'], check=True)
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to stop existing service: {e}")
            
            os.makedirs(user_systemd_dir, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(service_content)
            logger.info(f"Service file created at: {target_path}")
            logger.info(f"Using conda environment '{conda_env}' with command: {exec_command}")
            
            service_started = self._reload_user_systemd_and_enable_service()
            
            QMessageBox.information(
                self,
                "Success", 
                f"Service registered and enabled successfully!\n\n"
                f"Conda Environment: {conda_env}\n"
                f"Service Location: {target_path}\n\n"
                "The service will start automatically when you log in.\n\n"
                "You can also start it now with:\n"
                "systemctl --user start input-box.service"
            )
            logger.info("User service registered successfully")

            if service_started:
                self.__my_parent.quit_app()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to register service:\n{str(e)}"
            )
            logger.error(f"Failed to register service: {e}")
    
    def restart_service(self):
        """Restart the systemd user service."""
        try:
            subprocess.run(['systemctl', '--user', 'restart', 'input-box.service'], check=True)
            QMessageBox.information(
                self,
                "Service Restarted",
                "The input-box service has been restarted successfully."
            )
            logger.info("Service restarted successfully")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(
                self,
                "Restart Failed",
                f"Failed to restart the service:\n{str(e)}\n\n"
                "Please check if the service is properly installed:\n"
                "systemctl --user status input-box.service"
            )
            logger.error(f"Failed to restart service: {e}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while restarting the service:\n{str(e)}"
            )
            logger.error(f"Error restarting service: {e}")
    
    def is_service_enabled(self) -> bool:
        """Check if the input-box service is enabled for auto-startup."""
        try:
            # First check if the service exists
            result = subprocess.run(
                ['systemctl', '--user', 'list-unit-files', 'input-box.service'],
                capture_output=True,
                text=True
            )
            
            # If service doesn't exist, return True as default
            if result.returncode != 0 or 'input-box.service' not in result.stdout:
                logger.debug("Service does not exist, returning default value True")
                return True
            
            # If service exists, check if it's enabled
            result = subprocess.run(
                ['systemctl', '--user', 'is-enabled', 'input-box.service'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0 and result.stdout.strip() == 'enabled'
        except Exception as e:
            logger.warning(f"Failed to check service enabled status: {e}")
            return True  # Default
    
    def service_exists(self) -> bool:
        """Check if the input-box service exists."""
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'list-unit-files', 'input-box.service'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0 and 'input-box.service' in result.stdout
        except Exception as e:
            logger.warning(f"Failed to check service existence: {e}")
            return False
    
    def _reload_user_systemd_and_enable_service(self) -> bool:
        """Reload user systemd and enable service."""
        try:
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', '--user', 'enable', 'input-box.service'], check=True)
            try:
                subprocess.run(['systemctl', '--user', 'start', 'input-box.service'], check=True)
                logger.info("User systemd reloaded, service enabled and started")
                return True
            except subprocess.CalledProcessError as e:
                logger.warning(f"Service enabled but failed to start: {e}")
                logger.info("User systemd reloaded and service enabled")
                return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload user systemd or enable service: {e}")
            raise RuntimeError(f"Failed to reload user systemd or enable service: {e}")
        
    
    def _reload_systemd_and_enable_service(self) -> bool:
        """Reload systemd and enable service (when running as root)."""
        try:
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', 'enable', 'input-box.service'], check=True)
            try:
                subprocess.run(['systemctl', 'start', 'input-box.service'], check=True)
                logger.info("Systemd reloaded, service enabled and started")
                return True
            except subprocess.CalledProcessError as e:
                logger.warning(f"Service enabled but failed to start: {e}")
                logger.info("Systemd reloaded and service enabled")
                return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload systemd or enable service: {e}")
            raise RuntimeError(f"Failed to reload user systemd or enable service: {e}")
    
    def on_hotkey_recording_started(self):
        if self.parent_app and hasattr(self.parent_app, 'stop_hotkey_temporarily'):
            self.parent_app.stop_hotkey_temporarily()
    
    def on_hotkey_edit_finished(self):
        if self.parent_app and hasattr(self.parent_app, 'restart_hotkey_temporarily'):
            self.parent_app.restart_hotkey_temporarily()
    
    def accept(self):
        settings_dict = {
            "enable_hotkey": self.enable_hotkey_cb.isChecked(),
            "hotkey": self.hotkey_edit.keySequence().toString(),
            "hotkey_manager": self.hotkey_manager_combo.currentData(),
            "auto_paste": self.auto_paste_cb.isChecked(),
            "preserve_clipboard": self.preserve_clipboard_cb.isChecked(),
            "log_level": self.log_level_combo.currentText(),
            "auto_file_link": self.auto_file_link_cb.isChecked(),
            "target_directory": expand_path(self.target_dir_button.text()),
            "use_symlink": self.use_symlink_cb.isChecked(),
            "active_dismissal_behavior": self.active_dismissal_combo.currentData(),
            "passive_dismissal_behavior": self.passive_dismissal_combo.currentData()
        }
        
        # Handle auto-startup setting change (only when running under service and service exists)
        if is_running_under_service():
            # Check if service exists before trying to modify it
            if self.service_exists():
                current_enabled = self.is_service_enabled()
                new_setting = self.auto_startup_cb.isChecked()
                
                if current_enabled != new_setting:
                    try:
                        if new_setting:
                            subprocess.run(['systemctl', '--user', 'enable', 'input-box.service'], check=True)
                            logger.info("Auto-startup enabled for input-box service")
                        else:
                            subprocess.run(['systemctl', '--user', 'disable', 'input-box.service'], check=True)
                            logger.info("Auto-startup disabled for input-box service")
                        settings_dict["auto_startup"] = new_setting
                        
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to {'enable' if new_setting else 'disable'} auto-startup: {e}")
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"Failed to {'enable' if new_setting else 'disable'} auto-startup:\n{str(e)}\n\n"
                            "Settings will not be saved."
                        )
                        return
                    except Exception as e:
                        logger.error(f"Error handling auto-startup setting: {e}")
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"An error occurred while changing auto-startup setting:\n{str(e)}\n\n"
                            "Settings will not be saved."
                        )
                        return
                else:
                    settings_dict["auto_startup"] = new_setting
            else:
                # Service doesn't exist, just save the setting without system calls
                logger.debug("Service does not exist, saving auto-startup setting without system calls")
                settings_dict["auto_startup"] = self.auto_startup_cb.isChecked()
        else:
            # Not running under service, just save the setting
            settings_dict["auto_startup"] = self.auto_startup_cb.isChecked()
        
        save_settings_to_file(settings_dict)
        
        logger.info("Settings saved successfully")
        super().accept()
    
    def reject(self):
        # Restart hotkey listener if dialog is cancelled
        if self.parent_app and hasattr(self.parent_app, 'restart_hotkey_temporarily'):
            self.parent_app.restart_hotkey_temporarily()
        super().reject()
    
    def get_settings(self):
        settings = {
            'enable_hotkey': self.enable_hotkey_cb.isChecked(),
            'hotkey': self.hotkey_edit.keySequence().toString(),
            'hotkey_manager': self.hotkey_manager_combo.currentData(),
            'auto_paste': self.auto_paste_cb.isChecked(),
            'preserve_clipboard': self.preserve_clipboard_cb.isChecked(),
            'log_level': self.log_level_combo.currentText(),
            'auto_startup': self.auto_startup_cb.isChecked(),
            'auto_file_link': self.auto_file_link_cb.isChecked(),
            'target_directory': expand_path(self.target_dir_button.text()),
            'use_symlink': self.use_symlink_cb.isChecked(),
            'active_dismissal_behavior': self.active_dismissal_combo.currentData(),
            'passive_dismissal_behavior': self.passive_dismissal_combo.currentData()
        }
        
        return settings
