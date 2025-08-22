# InputBox — Help

This help file summarizes how to use InputBox and documents a few non-obvious features added since the project was first created. Read the short "File linking / sandbox workflow" section if you plan to use InputBox to help sandboxed applications open files.

## Quick start

1. Run the program:

   ```bash
   python main.py
   ```

2. Open the input window:

   Press the global hotkey (default: Ctrl+Q) or choose "Show Input" from the tray menu.

3. Type or paste text. Keyboard behavior inside the input window:

- Enter: submit the content (copies to clipboard and closes the window)
- Shift+Enter or Ctrl+Enter: insert a newline
- Esc: cancel/close (save behavior on cancel is configurable)

If the submitted text is a file path, InputBox will treat it as a file: it can copy file mime data to the clipboard (so target apps receive a file rather than plain text) and — if enabled — create a link in the configured target directory so sandboxed apps can access the linked file in the whitelisted location.

## Settings overview

Open the Settings dialog from the tray menu. Important settings:

- Enable hotkey / Hotkey: Toggle and configure the global activation hotkey.
- Hotkey Manager: Select the hotkey backend (Auto selects X11 keybinder when available, otherwise falls back to pynput).
- Auto paste: If enabled, the app will automatically simulate a paste (Ctrl+V) into the focused application after copying.
- Preserve clipboard: When enabled, the app will restore the previous clipboard contents after auto-paste.
- Log Level: Adjust logging verbosity; logs are written to `input-box.log`.

Advanced settings (open "Advanced Settings"):

- Enable automatic file linking: when a file is pasted or detected, create a hard link or symlink in the target directory.
- Target directory: where links will be created. This directory is intended to be whitelisted for sandboxed apps.
- Use symbolic links: prefer symlinks instead of hard links.
- Link management: open the cleanup dialog to view/remove created links safely.
- Input preservation: control whether Esc or focus loss saves the content and/or cursor position.

Notes about the hotkey manager:

- On X11 systems with the Keybinder libraries installed (gir1.2-keybinder-3.0), the app will prefer the X11 Keybinder backend, which provides more native behavior.
- If Keybinder is not available, the app falls back to the `pynput` backend.

## File linking (sandbox / whitelist use-case)

This is a short, practical guide explaining why InputBox has a "file linking" feature and how to use it.

Problem: sandboxed applications (firejail, Flatpak, Snap, etc.) often restrict filesystem access. When an app inside a sandbox needs to open or receive a file from your home directory, it may fail unless the file resides in a whitelisted location.

Solution provided by InputBox:

1. Configure a target directory (in Settings → Advanced) that your sandboxed app can access or that you've added to the sandbox whitelist. Example: `~/sandbox-files`.
2. Enable "Auto paste" and "Enable automatic file linking".
3. Paste a file (for example, from a file manager) or paste/type a file path into the InputBox dialog.
4. InputBox creates a hard link (or symlink, if you chose that option) in the target directory and writes file-type mime data to the clipboard pointing to that linked file.
5. Auto-paste will insert the file into the sandboxed application as if you had chosen the file from a file picker — but the application reads the file from the whitelisted target directory.

Important safety notes:

- InputBox records every created link in `input-box.config`. Use the "Clean Up Created Links" dialog to review and delete links.
- When deleting a hard link, InputBox checks whether it's the last link to the underlying file and warns before permanently deleting the file data.
- The app avoids overwriting existing files in the target directory by appending numeric suffixes when needed.

When to use this

- Use InputBox's file-linking when you need to quickly provide a file to a sandboxed app and don't want to manually copy files into the whitelist directory.
- This is intended to be a convenience for exceptional cases — maintain good sandboxing practices and clean up links when they are no longer needed.

## Systemd / service registration

From Settings you can register InputBox as a systemd user service. The registration dialog attempts to craft a sensible ExecStart that preserves your conda environment if one is detected. The generated unit is written to `~/.config/systemd/user/input-box.service` and the dialog can enable/start the service for you.

If systemd registration fails, check that you are running in the intended Python/conda environment and that `systemctl --user` is available.

## Link cleanup and safety

- Use the "Clean Up Created Links" action (from Settings → Advanced or from the InputDialog cleanup helper) to open the list of recorded links.
- You can select links to delete; if a selected hard link is the last reference to the file, InputBox will ask for explicit confirmation.

## Troubleshooting

- Hotkey not triggering: install Keybinder (X11) or allow the fallback pynput backend; check for global hotkey conflicts.
- Auto-paste not happening: ensure the "Auto paste" option is enabled and that the target application accepts simulated paste events.
- File linking not working: check that the Target Directory is writable and that the sandbox configuration actually whitelists it.
- Service registration problems: ensure CONDA environment variables are set or run the app in the correct environment.

## Quick tips

- Use the "Preserve Clipboard" option if you want the original clipboard restored after auto-paste.
- If you rely on a file whitelist for sandboxes, pick a consistent `Target directory` and add it to the sandbox configuration once; InputBox will manage putting files there for you.
