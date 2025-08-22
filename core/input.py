import os
import threading
import re
from PyQt6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget
from PyQt6.QtGui import QKeyEvent, QIcon
from PyQt6.QtCore import Qt, QEvent, QSettings, QMimeData, QUrl, QTimer
from pynput import keyboard
from pynput.keyboard import Key
from .tools import *


class CustomTextEdit(QTextEdit):
    def __init__(self, parent: "InputDialog"):
        super().__init__(None)
        self._input_dialog = parent
        self.setAcceptRichText(False)
    
    def insertFromMimeData(self, source):
        """Override to handle file paste detection and force plain text."""
        if not source:
            return
            
        if self._input_dialog and self._input_dialog.handle_file_paste(source):
            # File was processed, don't insert the original content
            return
        
        # For non-file content, only insert plain text
        if source.hasText():
            plain_text = source.text()
            self.insertPlainText(plain_text)
        # Not calling super() to avoid inserting rich content


class InputDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.set_window_icon()
        self.text_edit = CustomTextEdit(self)
        self.text_edit.setPlaceholderText("Type here...")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)
        self.text_edit.installEventFilter(self)
        config_path = os.path.join(ROOT, "input-box.config")
        self.settings = QSettings(config_path, QSettings.Format.IniFormat)
        
        self._saved_text = ""
        self._saved_cursor_position = 0
        self._saved_selection_start = 0
        self._saved_selection_end = 0
        self._should_select_all = False
        self._last_dismissal_was_active = True  # Track if last dismissal was active (Esc) or passive (focus loss)
    
    def save_current_state(self, behavior="content_and_cursor"):
        """Save current text and cursor position based on behavior setting.
        
        Args:
            behavior: "content_and_cursor", "content_only", or "no_save"
        """
        if behavior == "no_save":
            self._saved_text = ""
            self._saved_cursor_position = 0
            self._saved_selection_start = 0
            self._saved_selection_end = 0
            logger.debug("No state saved (no_save behavior)")
        elif behavior == "content_only":
            self._saved_text = self.text_edit.toPlainText()
            self._saved_cursor_position = 0
            self._saved_selection_start = 0
            self._saved_selection_end = 0
            logger.debug(f"Saved content only: {len(self._saved_text)} chars")
        else:
            self._saved_text = self.text_edit.toPlainText()
            cursor = self.text_edit.textCursor()
            self._saved_cursor_position = cursor.position()
            if cursor.hasSelection():
                self._saved_selection_start = cursor.selectionStart()
                self._saved_selection_end = cursor.selectionEnd()
                logger.debug(f"Saved content and cursor with selection: {len(self._saved_text)} chars, selection {self._saved_selection_start}-{self._saved_selection_end}")
            else:
                self._saved_selection_start = cursor.position()
                self._saved_selection_end = cursor.position()
                logger.debug(f"Saved content and cursor: {len(self._saved_text)} chars, cursor at {self._saved_cursor_position}")
    
    def restore_saved_state(self, save_mode):
        """Restore previously saved text and cursor position based on save mode."""
        if self._saved_text:
            self.text_edit.setPlainText(self._saved_text)
            if save_mode == "content_and_cursor":
                cursor = self.text_edit.textCursor()
                max_pos = len(self._saved_text)
                selection_start = min(self._saved_selection_start, max_pos)
                selection_end = min(self._saved_selection_end, max_pos)
                
                if selection_start != selection_end:
                    cursor.setPosition(selection_start)
                    cursor.setPosition(selection_end, cursor.MoveMode.KeepAnchor)
                    self.text_edit.setTextCursor(cursor)
                    logger.debug(f"Restored input state: {len(self._saved_text)} chars, selection {selection_start}-{selection_end}")
                else:
                    cursor_pos = min(self._saved_cursor_position, max_pos)
                    cursor.setPosition(cursor_pos)
                    self.text_edit.setTextCursor(cursor)
                    logger.debug(f"Restored input state: {len(self._saved_text)} chars, cursor at {cursor_pos}")
            elif save_mode == "content_only":
                self._should_select_all = True
                logger.debug(f"Restored input state: {len(self._saved_text)} chars, will select all")
            else:
                logger.critical("Restored input state: no valid save mode")

    def clear_saved_state(self):
        """Clear saved state (called when user presses Enter)."""
        self._saved_text = ""
        self._saved_cursor_position = 0
        self._saved_selection_start = 0
        self._saved_selection_end = 0
        self._last_dismissal_was_active = True
        logger.debug("Cleared saved input state")
    
    def get_dismissal_behavior(self, is_active=True):
        """Get the appropriate dismissal behavior based on settings.
        
        Args:
            is_active: True for active dismissal (Esc), False for passive dismissal (focus loss)
            
        Returns:
            Behavior string: "content_and_cursor", "content_only", or "no_save"
        """
        if is_active:
            return self.settings.value("active_dismissal_behavior", "content_and_cursor", str)
        else:
            passive_behavior = self.settings.value("passive_dismissal_behavior", "follow_active", str)
            if passive_behavior == "follow_active":
                return self.settings.value("active_dismissal_behavior", "content_and_cursor", str)
            else:
                return passive_behavior
    
    def hide_with_state_save(self, is_active=True):
        """Hide the dialog and save current state based on settings.
        
        Args:
            is_active: True for active dismissal (Esc), False for passive dismissal (focus loss)
        """
        behavior = self.get_dismissal_behavior(is_active)
        self.save_current_state(behavior)
        self._last_dismissal_was_active = is_active  # Record the dismissal type
        self.hide()
        dismissal_type = "active" if is_active else "passive"
        logger.debug(f"Hidden with {dismissal_type} dismissal ({behavior} behavior)")
    
    def ensure_focus(self):
        if self.isVisible():
            if not self.isActiveWindow() or not self.text_edit.hasFocus():
                saved_text = self.text_edit.toPlainText()
                cursor = self.text_edit.textCursor()
                saved_cursor_position = cursor.position()
                saved_has_selection = cursor.hasSelection()
                saved_selection_start = cursor.selectionStart() if saved_has_selection else cursor.position()
                saved_selection_end = cursor.selectionEnd() if saved_has_selection else cursor.position()
                saved_position = self.pos()
                
                self.hide()
                self.show()
                self.move(saved_position)
                self.raise_()
                self.activateWindow()
                
                self.text_edit.setPlainText(saved_text)
                
                if self._saved_text and saved_text == self._saved_text:
                    restore_behavior = self.get_dismissal_behavior(self._last_dismissal_was_active)
                    if restore_behavior == "content_only":
                        QTimer.singleShot(10, self.text_edit.selectAll)
                    elif restore_behavior == "content_and_cursor":
                        cursor = self.text_edit.textCursor()
                        max_pos = len(saved_text)
                        selection_start = min(self._saved_selection_start, max_pos)
                        selection_end = min(self._saved_selection_end, max_pos)
                        
                        if selection_start != selection_end:
                            cursor.setPosition(selection_start)
                            cursor.setPosition(selection_end, cursor.MoveMode.KeepAnchor)
                        else:
                            cursor_pos = min(self._saved_cursor_position, max_pos)
                            cursor.setPosition(cursor_pos)
                        self.text_edit.setTextCursor(cursor)
                else:
                    cursor = self.text_edit.textCursor()
                    max_pos = len(saved_text)
                    
                    if saved_has_selection:
                        start_pos = min(saved_selection_start, max_pos)
                        end_pos = min(saved_selection_end, max_pos)
                        cursor.setPosition(start_pos)
                        cursor.setPosition(end_pos, cursor.MoveMode.KeepAnchor)
                    else:
                        cursor_pos = min(saved_cursor_position, max_pos)
                        cursor.setPosition(cursor_pos)
                    self.text_edit.setTextCursor(cursor)
                    
                self.text_edit.setFocus()
        else:
            if self._saved_text:
                restore_behavior = self.get_dismissal_behavior(self._last_dismissal_was_active)
                self.restore_saved_state(restore_behavior)
            else:
                self.text_edit.clear()
                if self.text_edit.toPlainText():
                    self.text_edit.selectAll()
            self.show()
            self.raise_()
            self.activateWindow()
            self.text_edit.setFocus()
            
            if self._saved_text:
                restore_behavior = self.get_dismissal_behavior(self._last_dismissal_was_active)
                if restore_behavior == "content_only":
                    QTimer.singleShot(10, self.text_edit.selectAll)
    
    def clean_text(self, text: str) -> str:
        lines = text.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)
    
    def is_file_path(self, text: str) -> str | None:
        """Check if the text represents a file path."""
        cleaned_text = text.strip().strip('"\'')
        expanded_text = expand_path(cleaned_text)
        if os.path.isfile(expanded_text):
            return expanded_text
        if cleaned_text.startswith('file://'):
            try:
                url = QUrl(cleaned_text)
                local_file = url.toLocalFile()
                if os.path.isfile(local_file):
                    return local_file
            except:
                pass
        return None
    
    def create_file_link(self, source_file, target_dir, use_symlink=False):
        """Create a hard link or symbolic link for the file in the target directory."""
        try:
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            filename = os.path.basename(source_file)
            target_path = os.path.join(target_dir, filename)
            # Check if file already exists
            if os.path.exists(target_path):
                if use_symlink:
                    # For symlinks, only consider existing symlinks that point to the same file
                    if os.path.islink(target_path):
                        link_target = os.readlink(target_path)
                        if os.path.abspath(link_target) == os.path.abspath(source_file):
                            logger.info(f"Symbolic link already exists: {target_path}")
                            self.record_created_link(target_path, source_file, True)
                            return target_path
                else:
                    # For hard links, only consider existing hard links (same inode)
                    if not os.path.islink(target_path):
                        source_stat = os.stat(source_file)
                        target_stat = os.stat(target_path)
                        if source_stat.st_ino == target_stat.st_ino and source_stat.st_dev == target_stat.st_dev:
                            logger.info(f"Hard link already exists: {target_path}")
                            self.record_created_link(target_path, source_file, False)
                            return target_path
                counter = 1
                base_name, ext = os.path.splitext(filename)
                while os.path.exists(target_path):
                    new_filename = f"{base_name}_{counter}{ext}"
                    target_path = os.path.join(target_dir, new_filename)
                    counter += 1
            
            if use_symlink:
                os.symlink(source_file, target_path)
                logger.info(f"Created symbolic link: {source_file} -> {target_path}")
            else:
                os.link(source_file, target_path)
                logger.info(f"Created hard link: {source_file} -> {target_path}")
            self.record_created_link(target_path, source_file, use_symlink)
            
            return target_path
        
        except Exception as e:
            logger.error(f"Failed to create file link: {e}")
            return None
    
    def record_created_link(self, link_path, source_path, is_symlink):
        """Record a created link in the config file."""
        try:
            existing_links = self.get_created_links()
            if not link_path or not isinstance(link_path, str):
                logger.error(f"Invalid link_path: {link_path}")
                return
            if not source_path or not isinstance(source_path, str):
                logger.error(f"Invalid source_path: {source_path}")
                return
            link_info = {
                'link_path': link_path,
                'source_path': source_path,
                'is_symlink': bool(is_symlink),
                'created_time': os.path.getctime(link_path) if os.path.exists(link_path) else 0
            }
            for existing in existing_links:
                if isinstance(existing, dict) and existing.get('link_path') == link_path:
                    logger.debug(f"Link already recorded: {link_path}")
                    return
            
            existing_links.append(link_info)
            self.settings.setValue("created_links", existing_links)
            logger.debug(f"Recorded created link: {link_path} ({'symlink' if is_symlink else 'hardlink'})")
            
        except Exception as e:
            logger.error(f"Failed to record created link {link_path}: {e}")
    
    def get_created_links(self):
        """Get list of created links from config."""
        try:
            links = self.settings.value("created_links", [], list)
            if not isinstance(links, list):
                logger.warning("Invalid created_links format in config, resetting to empty list")
                self.settings.setValue("created_links", [])
                return []
            existing_links = []
            for link in links:
                try:
                    if not isinstance(link, dict):
                        logger.warning(f"Invalid link entry format: {link}")
                        continue
                    
                    if 'link_path' not in link or 'source_path' not in link:
                        logger.warning(f"Link entry missing required fields: {link}")
                        continue
                    
                    link_path = link['link_path']
                    if not isinstance(link_path, str) or not link_path:
                        logger.warning(f"Invalid link_path: {link_path}")
                        continue
                    
                    if os.path.exists(link_path):
                        existing_links.append(link)
                    else:
                        logger.debug(f"Link no longer exists: {link_path}")
                except Exception as e:
                    logger.warning(f"Error processing link entry {link}: {e}")
                    continue
            if len(existing_links) != len(links):
                self.settings.setValue("created_links", existing_links)
                logger.info(f"Cleaned up {len(links) - len(existing_links)} invalid/missing link entries")
            
            return existing_links
        except Exception as e:
            logger.error(f"Failed to get created links: {e}")
            self.settings.setValue("created_links", [])
            return []
    
    def cleanup_created_links(self):
        """Clean up created links with smart deletion logic."""
        from PyQt6.QtWidgets import (QDialog, QListWidget, QListWidgetItem, QVBoxLayout, 
                                     QHBoxLayout, QPushButton, QCheckBox, QLabel, QScrollArea, QWidget)
        
        links = self.get_created_links()
        if not links:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Links", "No created links found to clean up.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Clean Up Created Links")
        dialog.setModal(True)
        dialog.resize(700, 500)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        description_label = QLabel("Select links to delete:")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        checkboxes = []
        for link in links:
            link_path = link.get('link_path', '')
            source_path = link.get('source_path', '')
            is_symlink = link.get('is_symlink', False)
            
            if not link_path:
                continue
                
            link_type = "symlink" if is_symlink else "hardlink"
            display_text = f"{shorten_path(link_path)} ({link_type}) -> {shorten_path(source_path)}"
            
            checkbox = QCheckBox(display_text)
            setattr(checkbox, 'link_info', link)
            checkboxes.append(checkbox)
            scroll_layout.addWidget(checkbox)
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # Add buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")
        ok_btn = QPushButton("Delete Selected")
        cancel_btn = QPushButton("Cancel")
        
        def select_all():
            for cb in checkboxes:
                cb.setChecked(True)
        
        def select_none():
            for cb in checkboxes:
                cb.setChecked(False)
        
        def on_ok():
            links_to_delete = [getattr(cb, 'link_info') for cb in checkboxes if cb.isChecked()]
            dialog.accept()
            self.delete_selected_links(links_to_delete)
        
        select_all_btn.clicked.connect(select_all)
        select_none_btn.clicked.connect(select_none)
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()
    
    def delete_selected_links(self, links_to_delete):
        """Delete selected links with confirmation for files that would be physically deleted."""
        from PyQt6.QtWidgets import QMessageBox
        
        if not links_to_delete:
            return
        
        for link_info in links_to_delete:
            link_path = link_info['link_path']
            is_symlink = link_info.get('is_symlink', False)
            
            if not os.path.exists(link_path):
                logger.warning(f"Link no longer exists: {link_path}")
                continue
            
            should_delete = True
            
            if not is_symlink and os.path.exists(link_path):
                try:
                    link_stat = os.stat(link_path)
                    if link_stat.st_nlink <= 1:
                        reply = QMessageBox.question(
                            self, 
                            "Confirm File Deletion",
                            f"Deleting this hard link will permanently remove the file:\n{shorten_path(link_path)}\n\nThis is the last reference to the file. Are you sure?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.YesToAll | QMessageBox.StandardButton.NoToAll
                        )
                        
                        if reply == QMessageBox.StandardButton.No:
                            should_delete = False
                        elif reply == QMessageBox.StandardButton.NoToAll:
                            break
                        elif reply == QMessageBox.StandardButton.YesToAll:
                            pass
                            
                except Exception as e:
                    logger.error(f"Error checking link count for {link_path}: {e}")
            
            if should_delete:
                try:
                    os.remove(link_path)
                    logger.info(f"Deleted link: {link_path}")
                except Exception as e:
                    logger.error(f"Failed to delete link {link_path}: {e}")
                    QMessageBox.warning(self, "Deletion Failed", f"Failed to delete {shorten_path(link_path)}: {e}")
        remaining_links = []
        all_links = self.get_created_links()
        deleted_paths = {link['link_path'] for link in links_to_delete}
        
        for link in all_links:
            if link['link_path'] not in deleted_paths:
                remaining_links.append(link)
        
        self.settings.setValue("created_links", remaining_links)
        logger.info(f"Cleaned up {len(links_to_delete)} links")

    def detect_file_from_clipboard(self, mime_data):
        """Detect if the clipboard contains file data and return file path."""
        if not mime_data:
            return None
        if mime_data.hasUrls():
            urls = mime_data.urls()
            if urls:
                for url in urls:
                    if url.isLocalFile():
                        file_path = url.toLocalFile()
                        if os.path.isfile(file_path):
                            return file_path
        if mime_data.hasText():
            text = mime_data.text().strip()
            return self.is_file_path(text)
        return
    
    def create_file_mime_data(self, file_path):
        """Create QMimeData with proper file metadata."""
        mime_data = QMimeData()
        
        file_url = QUrl.fromLocalFile(file_path)
        mime_data.setUrls([file_url])
        mime_data.setText(file_path)
        try:
            file_list = f"file:///{file_path.replace(os.sep, '/')}\n"
            mime_data.setData("text/uri-list", file_list.encode('utf-8'))
            mime_data.setData("text/x-moz-url", f"{file_url.toString()}\n{os.path.basename(file_path)}".encode('utf-8'))
            mime_data.setData("application/x-kde-cutselection", b"0")  # 0 means copy, 1 means cut
            
        except Exception as e:
            logger.debug(f"Could not set additional file formats: {e}")
        
        return mime_data
    
    def process_file_content(self, text):
        """Process file content for auto file linking."""
        if not self.settings.value("auto_file_link", False, bool):
            return text
        
        file_path = self.is_file_path(text)
        if not file_path:
            return text
        
        target_dir = self.settings.value("target_directory", ROOT, str)
        use_symlink = self.settings.value("use_symlink", False, bool)
        
        linked_path = self.create_file_link(file_path, target_dir, use_symlink)
        if linked_path:
            logger.debug(f"File linked successfully: {file_path} -> {linked_path}")
            return linked_path
        else:
            logger.warning(f"Failed to link file: {file_path}")
            return text
    
    def handle_file_paste(self, mime_data):
        """Handle file paste immediately when detected."""
        if not self.settings.value("auto_file_link", False, bool):
            return False
        
        file_path = self.detect_file_from_clipboard(mime_data)
        if not file_path:
            return False
        
        target_dir = self.settings.value("target_directory", ROOT, str)
        use_symlink = self.settings.value("use_symlink", False, bool)
        
        linked_path = self.create_file_link(file_path, target_dir, use_symlink)
        if linked_path:
            logger.info(f"File automatically linked: {file_path} -> {linked_path}")
            clipboard = QApplication.clipboard()
            if clipboard:
                if self.settings.value("preserve_clipboard", True, bool):
                    original_mime_data = clipboard.mimeData()
                    if original_mime_data:
                        copied_mime_data = QMimeData()
                        for format_name in original_mime_data.formats():
                            copied_mime_data.setData(format_name, original_mime_data.data(format_name))
                
                new_mime_data = self.create_file_mime_data(linked_path)
                clipboard.setMimeData(new_mime_data)
            
            self.text_edit.setPlainText(shorten_path(linked_path))
            if self.settings.value("auto_paste", True, bool):
                def delayed_enter():
                    import time
                    time.sleep(0.05)
                    self.execute_enter_logic()
                threading.Thread(target=delayed_enter, daemon=True).start()
            return True
        else:
            logger.warning(f"Failed to link file during paste: {file_path}")
            return False
    
    def execute_enter_logic(self):
        """Execute the logic that happens when Enter is pressed."""
        raw_text = self.text_edit.toPlainText()
        cleaned_text = self.clean_text(raw_text)
        if cleaned_text and not re.match(r'^\s*$', cleaned_text):
            logger.debug(f"Processing text input: {len(cleaned_text)} characters")
            
            clipboard = QApplication.clipboard()
            if clipboard:
                original_clipboard_data = None
                if (self.settings.value("auto_paste", True, bool) and 
                    self.settings.value("preserve_clipboard", True, bool)):
                    original_mime_data = clipboard.mimeData()
                    if original_mime_data:
                        copied_mime_data = QMimeData()
                        for format_name in original_mime_data.formats():
                            copied_mime_data.setData(format_name, original_mime_data.data(format_name))
                        original_clipboard_data = copied_mime_data
                
                expanded_text = expand_path(cleaned_text)
                if os.path.isfile(expanded_text):
                    file_mime_data = self.create_file_mime_data(expanded_text)
                    clipboard.setMimeData(file_mime_data)
                    logger.debug("File data copied to clipboard with metadata")
                else:
                    clipboard.setText(expanded_text)
                    logger.debug("Text copied to clipboard")
                
                self.auto_paste(original_clipboard_data)
        
        # Clear saved state since user pressed Enter (successful completion)
        self.clear_saved_state()
        self.hide()
    
    def auto_paste(self, original_clipboard_data=None):
        if self.settings.value("auto_paste", True, bool):
            def paste_action():
                import time
                time.sleep(0.1)
                
                kb = keyboard.Controller()
                kb.press(Key.ctrl)
                kb.press('v')
                kb.release('v')
                kb.release(Key.ctrl)
                if (original_clipboard_data is not None and 
                    self.settings.value("preserve_clipboard", True, bool)):
                    time.sleep(0.2)
                    clipboard = QApplication.clipboard()
                    if clipboard:
                        clipboard.setMimeData(original_clipboard_data)
            
            threading.Thread(target=paste_action, daemon=True).start()
    
    def is_dark_mode(self):
        palette = QApplication.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        return bg_color.value() < 128
    
    def update_theme(self):
        if self.is_dark_mode():
            self.text_edit.setStyleSheet("""
                QTextEdit {
                    border: 2px solid #3498db;
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 14px;
                    background-color: #2b2b2b;
                    color: white;
                }
            """)
        else:
            self.text_edit.setStyleSheet("""
                QTextEdit {
                    border: 2px solid #3498db;
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 14px;
                    background-color: white;
                    color: black;
                }
            """)
        
    def showEvent(self, a0):
        super().showEvent(a0)
        self.update_theme()
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            self.move(screen_geometry.center() - self.rect().center())
        self.text_edit.setFocus()
        
        # Check if we should select all text based on restoration mode
        # This flag is set by restore_saved_state when content_only mode is used
        if hasattr(self, '_should_select_all') and self._should_select_all:
            self.text_edit.selectAll()
            self._should_select_all = False  # Reset the flag
        
        self.adjustSize()
        
    def eventFilter(self, a0, a1):
        if a0 == self.text_edit and a1 and a1.type() == QEvent.Type.KeyPress:
            if isinstance(a1, QKeyEvent):
                key_event = a1
                if key_event.key() == Qt.Key.Key_Return or key_event.key() == Qt.Key.Key_Enter:
                    modifiers = key_event.modifiers()
                    if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
                        self.text_edit.insertPlainText('\n')
                        self.adjustSize()
                        return True
                    else:
                        self.execute_enter_logic()
                        return True
                elif key_event.key() == Qt.Key.Key_Escape:
                    self.hide_with_state_save(is_active=True)  # Active dismissal (Esc key)
                    return True
        return super().eventFilter(a0, a1)
    
    def changeEvent(self, a0):
        """Handle window state changes including activation/deactivation."""
        super().changeEvent(a0)
        if a0 and a0.type() == QEvent.Type.ActivationChange:
            # Check if window lost activation (not active anymore)
            if not self.isActiveWindow() and self.isVisible():
                logger.debug("Window lost activation - auto-hiding")
                # Use QTimer to delay slightly in case it's just a temporary focus change
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(50, self._check_and_hide_on_focus_loss)
    
    def _check_and_hide_on_focus_loss(self):
        """Check if dialog should be hidden due to focus loss."""
        # Only hide if the dialog is still visible and doesn't have focus
        if self.isVisible() and not self.isActiveWindow() and not self.text_edit.hasFocus():
            logger.debug("Auto-hiding due to focus loss")
            self.hide_with_state_save(is_active=False)  # Passive dismissal (focus loss)
    
    def adjustSize(self):
        document = self.text_edit.document()
        if document:
            doc_size = document.size()
            doc_height = doc_size.height()
            self.text_edit.setFixedHeight(max(50, min(300, int(doc_height + 20))))
        super().adjustSize()
    
    def set_window_icon(self):
        """Set window icon using ROOT/icon.png if available, otherwise use Qt default."""
        icon_path = os.path.join(ROOT, "icon.png")
        if os.path.exists(icon_path):
            try:
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    logger.debug(f"Using window icon from {icon_path}")
                    return
                else:
                    logger.warning(f"Icon file exists but failed to load: {icon_path}")
            except Exception as e:
                logger.warning(f"Error loading window icon from {icon_path}: {e}")
        logger.debug("Using Qt default window icon (no dock icon)")

