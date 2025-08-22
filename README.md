# InputBox

A last-resort input solution for Linux applications with broken input method support.

![InputBox Demo](./icon.png)

## Overview

InputBox is a system tray application that provides an emergency input workaround when applications can't use standard input methods on Linux. This is designed as a **fallback solution** for problematic scenarios, not as a primary input tool.

**Use this only when normal input methods fail completely** - such as with security tools like firejail, broken IME implementations, or heavily sandboxed applications.

## Key Features

### � Emergency Input
- Global hotkey activation (default: `Ctrl+Q`)
- Fallback input interface when normal methods fail
- Automatic text copying to clipboard
- Optional auto-paste functionality

### Sandbox File Access
- Automatic file path detection and linking
- Create hard links or symbolic links for sandboxed applications
- Enables file access for applications with restricted filesystem access
- Link management and cleanup tools

### System Integration
- Systemd user service support
- Auto-startup on boot
- System tray integration
- Cross-session persistence

### User Experience
- Dark/light theme adaptation
- Customizable hotkeys
- Advanced settings panel
- Comprehensive logging

## Installation

### Prerequisites

# InputBox

Quick Input Tool — a compact system-tray utility that provides an emergency input window and helps sandboxed applications access files by creating links in a whitelisted directory.

![InputBox Demo](./icon.png)

## Summary

InputBox started as a small fallback input helper. Since then it gained a number of practical features:

- Global hotkey activation (default: `Ctrl+Q`, configurable)
- Lightweight frameless input dialog with multi-line support
- Automatic copy-to-clipboard and optional auto-paste (with optional clipboard preservation)
- Automatic file detection and "file linking" (create hardlinks or symlinks into a target, whitelisted directory)
- Link management UI (list and safely delete created links)
- Settings dialog with advanced options (hotkey backend selection, auto-linking, input preservation behavior)
- Pluggable hotkey backends (X11 keybinder when available, fallback to pynput)
- Optional systemd user service registration (auto-detects conda environment and writes a unit file)
- Robust logging with rotatable log file

## Main features (details)

- Activation: global hotkey to open the input dialog. Hotkey can be customized in Settings. Multiple hotkey backends are supported and selected automatically when possible.
- Input dialog: frameless, adapts to dark/light themes, supports Enter to submit, Shift+Enter/Ctrl+Enter for newlines, Esc to cancel. Input preservation modes control whether content and cursor are saved when the dialog is dismissed.
- Clipboard handling: submitted text is copied to the clipboard. If text is a file path, InputBox can write proper file mime data so target apps receive file metadata.
- Auto-paste: optionally simulates Ctrl+V after copying. Optionally preserves previous clipboard contents and restores them after paste.
- File linking (sandbox support): when enabled, InputBox detects file paths pasted into the dialog (or present in the clipboard), creates a hard link or symlink into a configured target directory, and replaces the clipboard content with a file-type mime so sandboxed apps can access the linked file in the whitelisted location.
- Link management: built-in UI to view created links and remove them safely (the app warns before deleting the last hard link to avoid data loss).
- Settings & systemd: settings persist in `input-box.config` (INI). The Settings dialog helps register a `~/.config/systemd/user/input-box.service` unit — the implementation attempts to detect conda environments and craft an ExecStart that preserves the environment.

## Installation

Prerequisites (examples for Debian/Ubuntu):

```bash
# keybinder packages are recommended for best hotkey support
sudo apt install gir1.2-keybinder-3.0 libkeybinder-3.0-0
```

Install Python requirements:

```bash
pip install -r requirements.txt
```

Requirements in this repo (example versions in `requirements.txt`):
- PyQt6
- pynput
- pygobject (for Keybinder integration)
- psutil

Run the app:

```bash
cd input-box-code
python main.py
```

## Usage

1. Run `python main.py` (or register as a systemd user service via Settings).
2. Press the global hotkey (default `Ctrl+Q`) or select "Show Input" from the tray menu.
3. Type or paste text. For file paths you can paste file icons/URLs — InputBox will detect and optionally create a link in the target directory.
4. Press `Enter` to copy the content (or file mime data) to the clipboard and optionally auto-paste into the focused application.

Keyboard shortcuts inside the dialog:

- Enter: submit (copy to clipboard and close)
- Shift+Enter / Ctrl+Enter: insert a newline
- Esc: cancel (behavior on cancel is configurable)

## File linking / sandbox workflow (short)

1. Enable "Auto paste" and "Automatic file linking" in Settings (Advanced).
2. Configure the "Target directory" — a directory you can add to the sandbox/whitelist (e.g., a folder your Flatpak or firejail profile allows).
3. Paste or type a file path (or paste a file from a file manager). InputBox will create a hardlink or symlink there and replace the clipboard with a file mime pointing to the linked file.
4. The sandboxed application can then open the linked file from the whitelisted location.

Notes: the app tries to avoid overwriting existing files, appends suffixes when necessary, records created links in the config, and provides a cleanup dialog to remove created links safely.

## Configuration files

- `input-box.config` — persistent settings (INI via QSettings)
- `input-box.log` — rotating log file
- Systemd user service: `~/.config/systemd/user/input-box.service` if registered

## Troubleshooting

- Hotkey not working: ensure keybinder libraries are installed (for X11) or allow the fallback pynput backend. Try another hotkey if conflict exists.
- Service registration fails: the settings dialog tries to detect conda; make sure your environment variables (CONDA_DEFAULT_ENV / CONDA_EXE) are available or run the app from the intended environment.
- File linking problems: verify the configured target directory exists and is writable; ensure the sandbox configuration actually whitelists that target directory.

## License

This project is licensed under GPLv3 — see the included `LICENSE` file.
