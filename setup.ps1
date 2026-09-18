$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Host 'Setting up Claude Limit Reset Monitor...' -ForegroundColor Cyan

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw 'Python was not found. Install Python 3.10+ from https://www.python.org/downloads/windows/ and try again.'
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creating virtual environment...' -ForegroundColor Yellow
    if ($python.Name -eq 'py.exe') {
        & $python.Source -3 -m venv .venv
    } else {
        & $python.Source -m venv .venv
    }
}

$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
Write-Host 'Upgrading pip...' -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip

Write-Host 'Installing Python packages...' -ForegroundColor Yellow
& $venvPython -m pip install pytesseract Pillow pyttsx3

$tesseract = Get-Command tesseract -ErrorAction SilentlyContinue
if ($tesseract) {
    Write-Host 'Tesseract OCR found.' -ForegroundColor Green
} else {
    $defaultTesseract = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if (Test-Path $defaultTesseract) {
        Write-Host "Tesseract found at $defaultTesseract." -ForegroundColor Green
    } else {
        Write-Warning 'Tesseract OCR was not found. Install it before running the monitor: https://github.com/UB-Mannheim/tesseract/wiki'
    }
}

Write-Host ''
Write-Host 'Setup complete.' -ForegroundColor Green
Write-Host 'Test the alert: .\run_monitor.bat --test-alert'
Write-Host 'Test OCR:       .\run_monitor.bat --calibrate'
Write-Host 'Start monitor:  .\run_monitor.bat'
