# Claude Token Reset Monitor — Setup

Watches your screen for a Claude usage-limit message, figures out when your limit resets, and alerts you (beep + spoken notification) the moment it does.

**Platform:** Windows (the beep sound uses `winsound`, built into Windows only). It will still run on macOS/Linux with beep replaced by a terminal bell and voice alerts still working via `pyttsx3`, but it hasn't been tuned for those platforms.

## 1. Install Tesseract OCR

The script reads text off your screen using Tesseract, which is separate from the Python package.

1. Download the Windows installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Run it, keep the default install location.
3. Open PowerShell and check it worked:
   ```
   tesseract --version
   ```
   If that prints a version number, you're done with this step.

If `tesseract --version` doesn't work (not on PATH), open `claude_token_monitor.py` and set:
```python
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## 2. Install Python dependencies

From the folder containing these files:
```
pip install -r requirements.txt
```

## 3. Calibrate before running the full monitor

This is the step most worth doing — it tells you whether OCR can actually read your screen correctly, without waiting around for a real limit message.

1. Open Claude (or paste some sample "usage limit" text somewhere visible) so something resembling a limit message is on screen.
2. Run:
   ```
   python claude_token_monitor.py --calibrate
   ```
3. It prints the exact text Tesseract extracted, and saves `calibration_screenshot.png` so you can see exactly what was captured.

If the printed text is garbled or missing the message entirely:
- Try increasing your OS display scaling / font size in the Claude window slightly — larger, higher-contrast text OCRs much better.
- Narrow `OCR_REGION` in the script to just the area around where Claude shows its limit message, instead of the whole screen (this also speeds up scanning). It's `(left, top, right, bottom)` in pixels — you can find these coordinates using the Windows Snipping Tool's crosshair coordinates, or by cropping `calibration_screenshot.png` in any image editor and noting the crop box.

## 4. Test the alert sound

Before leaving it running unattended, confirm you can actually hear it:
```
python claude_token_monitor.py --test-alert
```
If you hear nothing, check `VOICE_ENABLED` / `BEEP_ENABLED` in the script, and confirm your system volume isn't muted.

## 5. Run it

```
python claude_token_monitor.py
```

Leave it running in a terminal window. It scans every 10 seconds while hunting for a reset time, and backs off to scanning every 30 seconds once a reset time is locked in and the screen hasn't changed — so it's cheap to leave running in the background.

To stop it: `Ctrl+C`.

## Notes on reliability

- **Confirmation requirement:** a detected reset time only gets accepted after it's seen twice in a row (`REQUIRED_CONFIRMATIONS`), so a single bad OCR read won't schedule a wrong alert.
- **Conflict handling:** if a new OCR reading disagrees with an already-confirmed schedule, the original schedule wins and the new reading is logged as a warning — this protects against a stray misread knocking your alarm off course.
- **Crash/restart safety:** the currently scheduled reset is saved to `claude_token_monitor_state.json` after each confirmation, so restarting the script (or your PC) doesn't lose a pending alert.
- **Logs:** written to `claude_token_monitor.log`, capped at ~1 MB with one backup file, so it won't grow forever.

## Customizing

All the settings you're likely to want to change are constants near the top of `claude_token_monitor.py`:

| Setting | What it does |
|---|---|
| `OCR_REGION` | Limit scanning to a specific part of the screen |
| `SCAN_INTERVAL_SECONDS` / `IDLE_SCAN_INTERVAL_SECONDS` | How often it checks |
| `VOICE_ENABLED` / `BEEP_ENABLED` | Turn either notification type off |
| `REQUIRED_CONFIRMATIONS` | How many matching reads before trusting a detected time |
