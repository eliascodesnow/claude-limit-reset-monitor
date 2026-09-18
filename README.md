# Claude Limit Reset Monitor

A lightweight Windows utility that watches the visible Claude interface, uses OCR to detect a usage-limit message, reads the reset time, and alerts you when the reset occurs.

> **Windows only:** the monitor captures the screen with Pillow and uses Tesseract OCR. Keep the Claude window visible while it runs.

## Quick setup

### 1. Download the repository

Clone it with Git:

```powershell
git clone https://github.com/eliascodesnow/claude-limit-reset-monitor.git
cd claude-limit-reset-monitor
```

Or download the repository as a ZIP from GitHub and open PowerShell in the extracted folder.

### 2. Install Tesseract OCR

Install the Windows version of [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki), using the default installation location if possible.

Check that Windows can find it:

```powershell
tesseract --version
```

If that command is not recognized, find `tesseract.exe` (normally `C:\Program Files\Tesseract-OCR\tesseract.exe`) and set `TESSERACT_CMD` near the top of `reset_script.py`:

```python
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### 3. Run the setup script

Open PowerShell in the repository folder and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

The script creates a local `.venv` virtual environment and installs the required Python packages. It does not install Tesseract; install that separately in step 2.

If PowerShell blocks scripts permanently, use the one-time command above rather than changing the machine-wide policy.

### 4. Test the alert

```powershell
.\run_monitor.bat --test-alert
```

You should see a reset notification and hear the beep/voice alert. If you do not want voice alerts, set `VOICE_ENABLED = False` in `reset_script.py`.

### 5. Test OCR

Open Claude and make sure the usage-limit message or Claude interface is visible, then run:

```powershell
.\run_monitor.bat --calibrate
```

This saves `calibration_screenshot.png` and prints the text detected by OCR. Check that the output is readable.

### 6. Start monitoring

```powershell
.\run_monitor.bat
```

Leave the window open. Stop the monitor with `Ctrl+C`.

## Useful commands

Run these from the repository folder:

| Action | Command |
| --- | --- |
| Set up the virtual environment | `powershell -ExecutionPolicy Bypass -File .\setup.ps1` |
| Start monitoring | `.\run_monitor.bat` |
| Test the alert | `.\run_monitor.bat --test-alert` |
| Test OCR and take a screenshot | `.\run_monitor.bat --calibrate` |
| Stop the monitor | `Ctrl+C` |

If you prefer not to use the batch file, activate the environment and run Python directly:

```powershell
.\.venv\Scripts\Activate.ps1
python .\reset_script.py
```

## Improve OCR accuracy

The default setting scans the entire primary screen:

```python
OCR_REGION = None
```

After the basic test works, restrict scanning to the Claude area by setting a rectangle in `reset_script.py`:

```python
OCR_REGION = (left, top, right, bottom)
```

The values are screen coordinates in pixels: left, top, right, and bottom. A smaller region usually improves OCR accuracy and reduces CPU usage.

## Automatic startup (optional)

1. Press `Win+R`.
2. Enter `shell:startup` and press Enter.
3. Create a shortcut to `run_monitor.bat` in that folder.
4. In the shortcut properties, set **Start in** to the repository folder.

Make sure Tesseract is installed and the virtual environment has been created before enabling automatic startup.

## Files created while running

- `claude_token_monitor.log` — rotating monitor log.
- `claude_token_monitor_state.json` — saved reset state, allowing the monitor to resume after restarting.
- `calibration_screenshot.png` — created by `--calibrate`.

These files are local runtime data and do not need to be committed.

## Troubleshooting

### `python` or `py` is not recognized

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/) and enable **Add Python to PATH** during installation. Then run `setup.ps1` again.

### Tesseract could not be initialized

Run `tesseract --version`. If it fails, install Tesseract or set `TESSERACT_CMD` to the full path of `tesseract.exe` in `reset_script.py`.

### OCR output is empty or incorrect

Keep Claude visible, increase the Claude window size, run `--calibrate`, and set `OCR_REGION` to only the relevant part of the screen.

### No sound is played

Windows sound may be muted, or text-to-speech may be unavailable. The notification is also printed in the console and written to `claude_token_monitor.log`.

## How it works

The monitor periodically captures the visible screen, preprocesses the image, and sends it to Tesseract. It looks for Claude usage-limit phrases and parses either an absolute reset time (for example, `8:30 PM`) or a relative time (for example, `2 hours 15 minutes`). It requires two matching detections before scheduling an alert.

## License

No license has been specified yet. Add a license file before redistributing the project.
