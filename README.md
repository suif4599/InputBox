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

### 📁 Sandbox File Access
- Automatic file path detection and linking
- Create hard links or symbolic links for sandboxed applications
- Enables file access for applications with restricted filesystem access
- Link management and cleanup tools

### ⚙️ System Integration
- Systemd user service support
- Auto-startup on boot
- System tray integration
- Cross-session persistence

### 🎨 User Experience
- Dark/light theme adaptation
- Customizable hotkeys
- Advanced settings panel
- Comprehensive logging

## Installation

### Prerequisites

Make sure you have the following system packages installed:
```bash
# For hotkey functionality (Ubuntu/Debian)
sudo apt install gir1.2-keybinder-3.0 libkeybinder-3.0-0

# For other distributions, install equivalent keybinder packages
```

### Python Dependencies

1. Clone or download the repository
2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

Required packages:
- PyQt6 (6.9.1+)
- pynput (1.8.1+)
- pygobject (3.50.1-)
- psutil (7.0.0+)

### Running

```bash
cd input-box-code
python main.py
```

- Open system tray and click `Settings`
- Click `Register Service`

## Usage

### Basic Operation

1. **Start the application**: Run `python main.py`
2. **Activate input**: Press `Ctrl+Q` (or your configured hotkey)
3. **Type your text**: Use the input window that appears
4. **Submit**: Press `Enter` to copy text and close window
5. **Multi-line**: Use `Shift+Enter` or `Ctrl+Enter` for new lines
6. **Cancel**: Press `Esc` to close without copying

### File Handling for Sandboxed Applications

InputBox provides crucial file access capabilities for sandboxed applications:

- **Sandbox File Access**: Sandboxed applications (firejail, Flatpak, etc.) often can't access files from arbitrary locations
- **Link Creation**: Creates hard links or symbolic links in a designated target directory
- **Whitelist Solution**: Allows you to whitelist the target directory for sandbox access
- **Auto-linking**: Automatically detects file paths and creates accessible links
- **File metadata**: Preserves file information when copying to clipboard
- **Link cleanup**: Safely manage and remove created links

**Why this matters**: When a sandboxed application needs to access a file at `/home/user/documents/file.pdf`, it may be blocked. InputBox can create a link at `/home/user/sandbox-files/file.pdf` (your designated target directory), which you can then whitelist for sandbox access.

### System Service

For persistent operation, register InputBox as a systemd user service:

1. Open **Settings** from the tray menu
2. Click **Register Service**
3. The application will automatically:
   - Detect your conda environment
   - Create a systemd user service
   - Enable auto-startup on boot

## Configuration

Access settings through the system tray menu:

### Basic Settings
- **Enable Hotkey**: Toggle global activation
- **Hotkey**: Customize activation key combination
- **Auto Paste**: Automatically paste after copying
- **Preserve Clipboard**: Restore original clipboard content
- **Log Level**: Control logging verbosity

### Advanced Settings
- **Auto File Linking**: Enable automatic file link creation
- **Target Directory**: Set where file links are created
- **Use Symbolic Links**: Choose between hard links and symlinks
- **Link Management**: Clean up previously created links

## Configuration Files

- **Settings**: `input-box.config` (INI format)
- **Logs**: `input-box.log` (configurable log level)
- **Service**: `~/.config/systemd/user/input-box.service`

## Troubleshooting

### Common Issues

**Hotkey not working**
- Ensure keybinder packages are installed
- Check for hotkey conflicts with other applications
- Try a different key combination in settings

**Service registration fails**
- Make sure you're running from a conda environment
- Check conda environment variables are set
- Verify systemd user service support

**File linking not working**
- Enable "Auto Paste" in settings (required for auto file linking)
- Check target directory permissions
- Ensure source files exist and are accessible

**Application not starting**
- Check system tray is available
- Verify all dependencies are installed
- Check log file for error details

### Log Files

Check `input-box.log` for detailed error information. Adjust log level in settings for more verbose output.

## Requirements

- **OS**: Linux with X11 (XGrab) or others (pynput)
- **Python**: 3.10+

## License

This project is licensed under the GPLv3 License - see the [LICENSE](./LICENSE) file for details.

## Disclaimer

- This tool is designed as an **emergency fallback solution only**. 

- The file linking feature exists specifically to help sandboxed applications access files by creating links in whitelisted directories - it's not intended as a general file management tool.
