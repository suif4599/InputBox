# InputBox - Help Documentation

## Purpose
InputBox provides an emergency input workaround for applications that can't use standard input methods on Linux. This typically occurs when:
- Using security tools like firejail
- Running applications with broken IME support
- Working with sandboxed applications (e.g. firejail makes ibus-rime unaccessible)
- Applications missing required input modules

**Note**: This is an emergency fallback solution - always try fixing the underlying issue first. Don't use this as your primary input method.

## Basic Usage
1. Start the application:  
   `python main.py`
2. Activate input window:  
   **`Ctrl+Q`** (default hotkey)
3. Enter your text:  
   - Regular typing: Normal text input
   - New lines: **`Shift+Enter`** or **`Ctrl+Enter`**
   - File paths: Paste or type file paths for automatic processing
4. Submit text:  
   **`Enter`** → Copies to clipboard and closes window
   **`Esc`** → Close window without copying

## Settings

### Basic Settings
- **Enable Hotkey**: Toggle global activation shortcut
- **Hotkey**: Customize activation keys (only when enabled)
- **Auto Paste**: Automatically paste after copying (simulates Ctrl+V)
- **Preserve Clipboard**: Restore original clipboard after auto-paste
- **Log Level**: Control logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### System Service Settings
- **System Service**: Register/restart the application as a systemd user service
- **Auto-startup**: Enable/disable automatic startup on boot (requires service registration)

### Advanced Settings
- **Auto File Linking**: Automatically create links for file paths (requires Auto Paste)
- **Target Directory**: Directory where file links will be created
- **Use Symbolic Links**: Create symlinks instead of hard links
- **Link Management**: Clean up previously created links

## File Handling Features
InputBox provides file access solutions for sandboxed applications:
- **File Detection**: Automatically detects file paths in text or clipboard
- **Sandbox File Access**: Creates hard links or symbolic links in a target directory for sandboxed applications
- **Whitelist Solution**: Enables file access by creating links in directories that can be whitelisted for sandbox access
- **File Metadata**: Preserves file information when copying to clipboard
- **Link Cleanup**: Manages and removes created links with safety checks

**Why file linking?** Sandboxed applications (firejail, Flatpak, etc.) often can't access files from arbitrary locations. By creating links in a designated target directory, you can whitelist that directory for sandbox access, allowing the application to read files that would otherwise be blocked.

## System Service
InputBox supports running as a systemd user service for automatic startup:
- **Registration**: Automatically detects conda environment and creates service
- **Auto-startup**: Starts automatically when you log in
- **Background Operation**: Runs in background without terminal dependency

## Tray Menu
- **Show Input**: Open input window manually
- **Settings**: Configure application options
- **Help**: Show this documentation
- **Quit**: Exit application

## Keyboard Shortcuts
- **Global Hotkey**: `Ctrl+Q` (configurable) - Show input window
- **In Input Window**:
  - `Enter` - Submit text and close
  - `Shift+Enter` or `Ctrl+Enter` - Insert new line
  - `Esc` - Close without submitting

## Troubleshooting
- **Unable to use keybinder**: Make sure `gir1.2-keybinder-3.0` and `libkeybinder-3.0-0` is installed
- **Service registration fails**: Ensure you're running from a conda environment
- **File linking not working**: Check target directory permissions and enable auto paste
- **Hotkey conflicts**: Change hotkey in settings if conflicts with other applications
- **Input still not working**: Remember this is a fallback solution - try fixing the original input method problem first
