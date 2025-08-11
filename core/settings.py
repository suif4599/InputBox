import sys
import os
import subprocess
from PyQt6.QtWidgets import (QVBoxLayout, QDialog, QCheckBox, QLabel, QHBoxLayout,
                             QPushButton, QKeySequenceEdit, QMessageBox, QComboBox)
from PyQt6.QtGui import QKeySequence
from PyQt6.QtCore import QSettings

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .app import TrayInputApp

from .tools import *

class SettingsDialog(QDialog):
    def __init__(self, parent: "TrayInputApp"):
        super().__init__(None) # Must set to None
        self.__my_parent = parent
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 200)
        
        self.parent_app = parent
        config_path = os.path.join(ROOT, "input-box.config")
        self.settings = QSettings(config_path, QSettings.Format.IniFormat)
        
        layout = QVBoxLayout()
        self.enable_hotkey_cb = QCheckBox("Enable hotkey activation")
        self.enable_hotkey_cb.setChecked(self.settings.value("enable_hotkey", True, bool))
        layout.addWidget(self.enable_hotkey_cb)
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
        self.on_auto_paste_toggled(self.auto_paste_cb.isChecked())
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

        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def on_auto_paste_toggled(self, checked):
        self.preserve_clipboard_cb.setEnabled(checked)
        if not checked:
            self.preserve_clipboard_cb.setChecked(False)
        else:
            self.preserve_clipboard_cb.setChecked(True)
    
    def on_enable_hotkey_toggled(self, checked):
        self.hotkey_edit.setEnabled(checked)
    
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
Environment="XDG_SESSION_TYPE=x11"
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
        # Save settings
        self.settings.setValue("enable_hotkey", self.enable_hotkey_cb.isChecked())
        self.settings.setValue("hotkey", self.hotkey_edit.keySequence().toString())
        self.settings.setValue("auto_paste", self.auto_paste_cb.isChecked())
        self.settings.setValue("preserve_clipboard", self.preserve_clipboard_cb.isChecked())
        self.settings.setValue("log_level", self.log_level_combo.currentText())
        
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
                        self.settings.setValue("auto_startup", new_setting)
                        
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
                    self.settings.setValue("auto_startup", new_setting)
            else:
                # Service doesn't exist, just save the setting without system calls
                logger.debug("Service does not exist, saving auto-startup setting without system calls")
                self.settings.setValue("auto_startup", self.auto_startup_cb.isChecked())
        else:
            # Not running under service, just save the setting
            self.settings.setValue("auto_startup", self.auto_startup_cb.isChecked())
        
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
            'auto_paste': self.auto_paste_cb.isChecked(),
            'preserve_clipboard': self.preserve_clipboard_cb.isChecked(),
            'log_level': self.log_level_combo.currentText(),
            'auto_startup': self.auto_startup_cb.isChecked()
        }
        
        return settings
