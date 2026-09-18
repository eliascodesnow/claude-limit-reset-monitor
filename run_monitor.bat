@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Run this first: powershell -ExecutionPolicy Bypass -File .\setup.ps1
    exit /b 1
)

.venv\Scripts\python.exe reset_script.py %*
endlocal
