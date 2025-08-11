# InputBox - Help Documentation

## Purpose
InputBox provides a workaround for applications that can't use standard input methods on Linux. This typically occurs when:
- Using security tools like firejail
- Running applications with broken IME support
- Working with sandboxed applications (Flatpak/Snap)
- Applications missing required input modules

**Note**: This should be your last resort solution - always try fixing the underlying issue first.

## Basic Usage
1. Start the application:  
   `python main.py`
2. Activate input window:  
   **`Ctrl+Q`** (default hotkey)
3. Enter your text:  
   - Regular typing: Normal text input
   - New lines: **`Shift+Enter`** or **`Ctrl+Enter`**
4. Submit text:  
   **`Enter`** → Copies to clipboard and closes window

## Settings
- **Enable Hotkey**: Toggle global activation shortcut
- **Hotkey**: Customize activation keys (only when enabled)
- **Auto Paste**: Automatically paste after copying (simulates Ctrl+V)
- **Preserve Clipboard**: Restore original clipboard after auto-paste

## Tray Menu
- **Show Input**: Open input window manually
- **Settings**: Configure application options
- **Help**: Show this documentation
- **Quit**: Exit application

## Trouble Shooting
- **Unable to use keybinder**: Make sure `gir1.2-keybinder-3.0` and `libkeybinder-3.0-0` is installed
