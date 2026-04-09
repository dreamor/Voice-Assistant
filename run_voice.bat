@echo off
cd /d "%~dp0"

echo ================================================
echo   Voice Assistant Launcher
echo ================================================
echo.

set PYTHON=python3.12
where %PYTHON% >nul 2>&1
if %errorlevel% neq 0 set PYTHON=python

echo [INFO] Using: %PYTHON%

if not exist ".venv" (
    echo [INFO] Creating virtual environment with %PYTHON%...
    %PYTHON% -m venv .venv
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Failed to create virtual environment
    echo Try installing Python 3.12: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Installing dependencies...
.venv\Scripts\python.exe -m pip install -e .

if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Copying .env.example to .env
        copy .env.example .env
    )
)

echo.
echo ================================================
echo   Starting Voice Assistant...
echo ================================================
echo.

.venv\Scripts\python.exe run.py

pause