import os
import threading
import re
from PyQt6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtCore import Qt, QEvent, QSettings, QMimeData
from pynput import keyboard
from pynput.keyboard import Key
from .tools import *


class InputDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Type here...")
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)
        self.text_edit.installEventFilter(self)
        config_path = os.path.join(ROOT, "input-box.config")
        self.settings = QSettings(config_path, QSettings.Format.IniFormat)
    
    def clean_text(self, text):
        lines = text.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)
    
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
        self.text_edit.selectAll()
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
                                clipboard.setText(cleaned_text)
                                self.auto_paste(original_clipboard_data)
                                logger.debug("Text copied to clipboard and auto-paste triggered")
                        self.hide()
                        return True
                elif key_event.key() == Qt.Key.Key_Escape:
                    self.hide()
                    return True
        return super().eventFilter(a0, a1)
    
    def adjustSize(self):
        document = self.text_edit.document()
        if document:
            doc_size = document.size()
            doc_height = doc_size.height()
            self.text_edit.setFixedHeight(max(50, min(300, int(doc_height + 20))))
        super().adjustSize()

