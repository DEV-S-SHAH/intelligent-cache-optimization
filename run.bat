@echo off
REM ================================================================================
REM   Intelligent Cache Optimization - Windows Launcher (Command Prompt / PowerShell)
REM ================================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3"
    ) else (
        echo [ERROR] Python is not found in PATH. Please install Python 3.9+ and add to PATH.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creating Python virtual environment in .venv...
    %PY_CMD% -m venv .venv
    call .venv\Scripts\activate.bat
    echo [INFO] Installing package and dependencies...
    python -m pip install --upgrade pip
    pip install -e .
    if exist requirements.txt (
        pip install -r requirements.txt
    )
) else (
    call .venv\Scripts\activate.bat
)

python run.py %*

