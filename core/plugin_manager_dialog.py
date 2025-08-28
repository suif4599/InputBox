"""
Plugin management dialog for InputBox application.
"""
import os
from typing import TYPE_CHECKING, Any
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QCheckBox, QScrollArea, QWidget,
                             QFrame, QMessageBox, QTextEdit, QSizePolicy)
from PyQt6.QtGui import QFont, QIcon, QFontMetrics
from PyQt6.QtCore import Qt, pyqtSignal

if TYPE_CHECKING:
    from .app import TrayInputApp

from .tools import ROOT
from interface import CallbackContext
from plugins import get_plugin_manager


class PluginWidget(QFrame):
    """Widget representing a single plugin in the list."""
    
    toggled = pyqtSignal(str, bool)  # plugin_name, enabled
    settings_requested = pyqtSignal(str)  # plugin_name
    
    def __init__(self, plugin_info: dict[str, Any], parent=None):
        super().__init__(parent)
        self.plugin_info = plugin_info
        self.setup_ui()
    
    def setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMaximumHeight(80)
        self.setMinimumHeight(80)
        
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        size_policy.setHorizontalStretch(1)
        self.setSizePolicy(size_policy)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Enable/Disable checkbox
        self.checkbox = QCheckBox("Enabled")
        self.checkbox.setChecked(self.plugin_info['enabled'])
        self.checkbox.toggled.connect(self._on_toggled)
        controls_layout.addWidget(self.checkbox)
        
        # Settings button (gear icon)
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(30, 30)
        self.settings_btn.setToolTip("Plugin Settings")
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        
        # Disable settings if plugin has no settings
        plugin_instance = self.plugin_info['plugin_instance']
        has_settings = (plugin_instance.settings is not None or 
                       plugin_instance.settings_schema is not None or 
                       bool(plugin_instance.default_settings))
        self.settings_btn.setEnabled(has_settings)
        
        controls_layout.addWidget(self.settings_btn)
        
        # Create controls widget with fixed size
        self.controls_widget = QWidget()
        self.controls_widget.setLayout(controls_layout)
        controls_hint = self.controls_widget.sizeHint()
        self.controls_widget.setFixedWidth(controls_hint.width() + 20)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        self.name_label = QLabel()
        name_font = QFont()
        name_font.setPointSize(11)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        self.name_label.setWordWrap(False)
        name_size_policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.name_label.setSizePolicy(name_size_policy)
        info_layout.addWidget(self.name_label)
        
        # Plugin description and version (small font)
        self.desc_label = QLabel()
        desc_font = QFont()
        desc_font.setPointSize(9)
        self.desc_label.setFont(desc_font)
        self.desc_label.setStyleSheet("color: #666;")
        self.desc_label.setWordWrap(False)
        desc_size_policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.desc_label.setSizePolicy(desc_size_policy)
        info_layout.addWidget(self.desc_label)
        
        # Status indicator for disabled plugins
        self.status_label = QLabel()
        status_font = QFont()
        status_font.setPointSize(9)
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        self.status_label.setWordWrap(False)
        status_size_policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label.setSizePolicy(status_size_policy)
        info_layout.addWidget(self.status_label)
        
        self.info_widget = QWidget()
        self.info_widget.setLayout(info_layout)
        info_size_policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.info_widget.setSizePolicy(info_size_policy)
        layout.addWidget(self.info_widget, 1)  # stretch=1，floating width
        layout.addWidget(self.controls_widget, 0)  # stretch=0，fixed width
        self.setLayout(layout)
        self.update_text()
    
    def update_text(self):
        """Update text content based on current widget size."""
        total_width = self.width()
        controls_width = self.controls_widget.width()
        margins = 20
        available_width = max(50, total_width - controls_width - margins)
        
        desc_parts = []
        if self.plugin_info.get('version'):
            desc_parts.append(f"v{self.plugin_info['version']}")
        if self.plugin_info.get('author'):
            desc_parts.append(f"by {self.plugin_info['author']}")
        
        if desc_parts:
            desc_text = " • ".join(desc_parts)
        else:
            desc_text = ""
            
        if self.plugin_info.get('description'):
            if desc_text:
                desc_text += " • "
            desc_text += self.plugin_info['description']
        
        name_text = self.plugin_info['name']
        truncated_name = self._truncate_text_to_width(name_text, available_width, self.name_label.font())
        self.name_label.setText(truncated_name)
        if truncated_name != name_text:
            self.name_label.setToolTip(name_text)
        else:
            self.name_label.setToolTip("")
        
        if desc_text:
            truncated_desc = self._truncate_text_to_width(desc_text, available_width, self.desc_label.font())
            self.desc_label.setText(truncated_desc)
            if truncated_desc != desc_text:
                self.desc_label.setToolTip(desc_text)
            else:
                self.desc_label.setToolTip("")
            self.desc_label.setVisible(True)
        else:
            self.desc_label.setVisible(False)
        
        if not self.plugin_info['enabled']:
            status_text = "(Disabled)"
            truncated_status = self._truncate_text_to_width(status_text, available_width, self.status_label.font())
            self.status_label.setText(truncated_status)
            self.status_label.setStyleSheet("color: #999; font-weight: bold;")
            if truncated_status != status_text:
                self.status_label.setToolTip(status_text)
            else:
                self.status_label.setToolTip("")
            self.status_label.setVisible(True)
        else:
            self.status_label.setVisible(False)
    
    def _truncate_text_to_width(self, text: str, max_width: int, font: QFont) -> str:
        """Truncate text to fit within specified width."""
        metrics = QFontMetrics(font)
        
        if metrics.horizontalAdvance(text) <= max_width:
            return text
        left, right = 0, len(text)
        while left < right:
            mid = (left + right + 1) // 2
            test_text = text[:mid] + "..."
            if metrics.horizontalAdvance(test_text) <= max_width:
                left = mid
            else:
                right = mid - 1
        
        return text[:left] + "..." if left > 0 else "..."
    
    def _on_toggled(self, checked: bool):
        """Handle checkbox toggle."""
        self.toggled.emit(self.plugin_info['name'], checked)
    
    def _on_settings_clicked(self):
        """Handle settings button click."""
        self.settings_requested.emit(self.plugin_info['name'])
    
    def update_enabled_state(self, enabled: bool):
        """Update the plugin enabled state."""
        self.plugin_info['enabled'] = enabled
        self.checkbox.setChecked(enabled)
        self.update_text()  # Update status display
    
    def resizeEvent(self, a0):
        """Handle resize events to update text truncation."""
        super().resizeEvent(a0)
        if hasattr(self, 'name_label'):
            self.update_text()


class PluginSettingsDialog(QDialog):
    """Dialog for viewing/editing plugin settings."""
    
    def __init__(self, plugin_info: dict[str, Any], parent=None):
        super().__init__(parent)
        self.plugin_info = plugin_info
        self.plugin_instance = plugin_info['plugin_instance']
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle(f"Plugin Settings - {self.plugin_info['name']}")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout()
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout()
        name_label = QLabel(self.plugin_info['name'])
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        name_label.setFont(name_font)
        info_layout.addWidget(name_label)
        
        version_label = QLabel(f"Version: {self.plugin_info['version']}")
        info_layout.addWidget(version_label)
        author_label = QLabel(f"Author: {self.plugin_info['author']}")
        info_layout.addWidget(author_label)
        
        if self.plugin_info['description']:
            desc_label = QLabel(f"Description: {self.plugin_info['description']}")
            desc_label.setWordWrap(True)
            info_layout.addWidget(desc_label)
        
        info_frame.setLayout(info_layout)
        layout.addWidget(info_frame)
        
        # Settings section
        settings_label = QLabel("Settings:")
        settings_font = QFont()
        settings_font.setBold(True)
        settings_label.setFont(settings_font)
        layout.addWidget(settings_label)
        
        # Check if plugin has settings
        if self.plugin_instance.settings:
            settings_info = self.plugin_instance.settings
            settings_text = f"Display Name: {settings_info.display_name}\n"
            if settings_info.description:
                settings_text += f"Description: {settings_info.description}\n"
            if settings_info.default_config:
                settings_text += f"Default Config: {settings_info.default_config}\n"
            
            settings_edit = QTextEdit()
            settings_edit.setPlainText(settings_text)
            settings_edit.setReadOnly(True)
            layout.addWidget(settings_edit)
        elif self.plugin_instance.settings_schema or self.plugin_instance.default_settings:
            # Legacy settings support
            settings_text = ""
            if self.plugin_instance.settings_schema:
                settings_text += f"Schema: {self.plugin_instance.settings_schema}\n"
            if self.plugin_instance.default_settings:
                settings_text += f"Default Settings: {self.plugin_instance.default_settings}\n"
            
            settings_edit = QTextEdit()
            settings_edit.setPlainText(settings_text)
            settings_edit.setReadOnly(True)
            layout.addWidget(settings_edit)
        else:
            no_settings_label = QLabel("This plugin has no configurable settings.")
            no_settings_label.setStyleSheet("color: #666; font-style: italic;")
            layout.addWidget(no_settings_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)


class PluginManagerDialog(QDialog):
    """Main plugin management dialog."""
    
    def __init__(self, parent: "TrayInputApp"):
        super().__init__(None)
        self.app = parent
        self.plugin_manager = get_plugin_manager()
        self.plugin_widgets: dict[str, PluginWidget] = {}
        self.pending_changes: dict[str, bool] = {}  # plugin_name -> enabled_state
        self.original_states: dict[str, bool] = {}  # Store original states
        self.setup_ui()
        self._handle_plugin_changes()
        self.load_plugins()
    
    def _handle_plugin_changes(self):
        """Handle new, deleted, and renamed plugins."""
        if not self.plugin_manager:
            return
        
        changes = self.plugin_manager.check_for_plugin_changes()
        
        if changes.get('renamed'):
            context = CallbackContext(app=self.app, logger=self.plugin_manager.logger)
            renamed_names = self.plugin_manager.handle_renamed_plugins(changes['renamed'], context)
            
            if renamed_names:
                renamed_list = '\n'.join(f"• {name}" for name in renamed_names)
                QMessageBox.information(
                    self, "Plugin Status Changed", 
                    f"The following plugins had their enabled/disabled status changed:\n\n{renamed_list}\n\nTheir callbacks have been updated accordingly."
                )
        
        if changes['deleted']:
            context = CallbackContext(app=self.app, logger=self.plugin_manager.logger)
            deleted_names = self.plugin_manager.handle_deleted_plugins(changes['deleted'], context)
            if deleted_names:
                deleted_list = '\n'.join(f"• {name}" for name in deleted_names)
                QMessageBox.information(
                    self, "Plugins Deleted", 
                    f"The following plugins have been deleted:\n\n{deleted_list}\n\nTheir exit callbacks have been triggered."
                )
        
        if changes['new']:
            new_disabled = [name for name in changes['new'] if not name.endswith('.disabled')]
            if new_disabled:
                new_list = '\n'.join(f"• {name}" for name in new_disabled)
                QMessageBox.information(
                    self, "New Plugins Found", 
                    f"New plugins have been found and automatically disabled:\n\n{new_list}\n\nYou can enable them from the plugin manager."
                )
    
    def setup_ui(self):
        self.setWindowTitle("Plugin Manager")
        self.setModal(True)
        self.resize(700, 600)
        
        icon_path = os.path.join(ROOT, "icon.png")
        if os.path.exists(icon_path):
            try:
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
            except Exception:
                pass
        
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Plugin Manager")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        
        # Refresh button in header
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_plugins)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)
        
        # Info label
        info_label = QLabel("Make your changes and click OK to apply them, or Cancel to discard.")
        info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info_label)
        
        # Plugin list in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.plugins_widget = QWidget()
        self.plugins_layout = QVBoxLayout()
        self.plugins_layout.setSpacing(5)
        self.plugins_widget.setLayout(self.plugins_layout)
        
        scroll_area.setWidget(self.plugins_widget)
        layout.addWidget(scroll_area, 1)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.apply_changes_and_close)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_plugins(self):
        """Load and display all plugins."""
        if not self.plugin_manager:
            no_manager_label = QLabel("Plugin manager not available.")
            no_manager_label.setStyleSheet("color: red; font-style: italic;")
            self.plugins_layout.addWidget(no_manager_label)
            return
        
        plugins_info = self.plugin_manager.get_all_plugins_info()
        
        if not plugins_info:
            no_plugins_label = QLabel("No plugins found.")
            no_plugins_label.setStyleSheet("color: #666; font-style: italic;")
            self.plugins_layout.addWidget(no_plugins_label)
            return
        
        plugins_info.sort(key=lambda p: (not p['enabled'], p['name'].lower()))
        
        for plugin_info in plugins_info:
            self.original_states[plugin_info['name']] = plugin_info['enabled']
            widget = PluginWidget(plugin_info, self)
            widget.toggled.connect(self.on_plugin_toggled)
            widget.settings_requested.connect(self.on_plugin_settings_requested)
            
            self.plugin_widgets[plugin_info['name']] = widget
            self.plugins_layout.addWidget(widget)
        
        self.plugins_layout.addStretch()
    
    def refresh_plugins(self):
        """Refresh the plugin list."""
        for widget in self.plugin_widgets.values():
            widget.deleteLater()
        self.plugin_widgets.clear()
        self.pending_changes.clear()
        self.original_states.clear()
        
        while self.plugins_layout.count():
            child = self.plugins_layout.takeAt(0)
            if child and child.widget():
                widget = child.widget()
                if widget:
                    widget.deleteLater()
        
        if self.plugin_manager:
            self.plugin_manager.load_plugins()
        
        self._handle_plugin_changes()
        
        self.load_plugins()
    
    def on_plugin_toggled(self, plugin_name: str, enabled: bool):
        """Handle plugin enable/disable toggle - store pending change."""
        original_state = self.original_states.get(plugin_name, False)
        
        if enabled != original_state:
            self.pending_changes[plugin_name] = enabled
        else:
            if plugin_name in self.pending_changes:
                del self.pending_changes[plugin_name]
        widget = self.plugin_widgets.get(plugin_name)
        if widget:
            widget.update_enabled_state(enabled)
    
    def apply_changes_and_close(self):
        """Apply all pending changes and close the dialog."""
        if not self.plugin_manager or not self.pending_changes:
            self.accept()
            return
        
        try:
            context = CallbackContext(app=self.app, logger=self.plugin_manager.logger)
            failed_plugins = []
            for plugin_name, enabled in self.pending_changes.items():
                try:
                    success = self.plugin_manager.set_plugin_enabled(plugin_name, enabled, context)
                    if success:
                        status = "enabled" if enabled else "disabled"
                        self.plugin_manager.logger.info(f"Plugin '{plugin_name}' {status}")
                    else:
                        failed_plugins.append(plugin_name)
                except Exception as e:
                    self.plugin_manager.logger.error(f"Error changing plugin {plugin_name}: {e}")
                    failed_plugins.append(plugin_name)
            
            if failed_plugins:
                failed_list = '\n'.join(f"• {name}" for name in failed_plugins)
                QMessageBox.critical(
                    self, "Error", 
                    f"Failed to apply changes to the following plugins:\n{failed_list}"
                )
            self.accept()
            
        except Exception as e:
            self.plugin_manager.logger.error(f"Error applying plugin changes: {e}")
            QMessageBox.critical(
                self, "Error", 
                f"Failed to apply plugin changes:\n{str(e)}"
            )
    
    def on_plugin_settings_requested(self, plugin_name: str):
        """Handle plugin settings request."""
        plugins_info = self.plugin_manager.get_all_plugins_info() if self.plugin_manager else []
        
        plugin_info = None
        for info in plugins_info:
            if info['name'] == plugin_name:
                plugin_info = info
                break
        
        if not plugin_info:
            QMessageBox.warning(
                self, "Error", 
                f"Plugin '{plugin_name}' not found."
            )
            return
        
        settings_dialog = PluginSettingsDialog(plugin_info, self)
        settings_dialog.exec()
