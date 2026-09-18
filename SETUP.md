# Claude Token Reset Monitor

## 1. Create the folder

Open PowerShell and run:

```powershell
mkdir claude-token-monitor
cd claude-token-monitor
```

## 2. Put the Python script in the folder

Save your script as:

```text
claude_token_monitor.py
```

Your folder should now contain:

```text
claude-token-monitor/
└── claude_token_monitor.py
```

## 3. Install the Python packages

Run:

```powershell
python -m pip install pytesseract Pillow pyttsx3
```

If `python` does not work, use:

```powershell
py -m pip install pytesseract Pillow pyttsx3
```

## 4. Install Tesseract OCR

Install Tesseract OCR for Windows.

Then test it:

```powershell
tesseract --version
```

If that works, leave this in your Python script:

```python
TESSERACT_CMD = None
```

If it does not work, find your `tesseract.exe` and change the setting to something like:

```python
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## 5. Test the notification

Run:

```powershell
python claude_token_monitor.py --test-alert
```

You should hear:

```text
Your Claude tokens have been reset.
```

along with the beep sequence.

## 6. Test OCR

Open Claude and make sure the relevant Claude interface is visible.

Run:

```powershell
python claude_token_monitor.py --calibrate
```

The script will create:

```text
calibration_screenshot.png
```

and print the OCR text in PowerShell.

Check that the text is being read correctly.

## 7. Start the monitor

Run:

```powershell
python claude_token_monitor.py
```

You should see:

```text
Claude Token Reset Monitor started.
Monitoring screen for Claude usage limits.
```

Leave the program running.

## 8. Optional: restrict OCR to Claude

Start with:

```python
OCR_REGION = None
```

Once everything works, you can replace it with:

```python
OCR_REGION = (left, top, right, bottom)
```

using the coordinates of the Claude area on your screen.

## 9. Optional: start automatically with Windows

Create:

```text
start_monitor.bat
```

Put this inside:

```bat
@echo off
cd /d "C:\path\to\claude-token-monitor"
python claude_token_monitor.py
```

Replace the path with your actual folder.

Then press:

```text
Win + R
```

and enter:

```text
shell:startup
```

Put a shortcut to `start_monitor.bat` there.

## 10. Normal commands

Start monitor:

```powershell
python claude_token_monitor.py
```

Test alert:

```powershell
python claude_token_monitor.py --test-alert
```

Test OCR:

```powershell
python claude_token_monitor.py --calibrate
```

Stop:

```text
Ctrl + C
```
