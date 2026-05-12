@echo off
chcp 65001 >nul 2>&1
setlocal

cd /d "%~dp0"

if "%1"=="" goto mode_web
if "%1"=="--help" goto show_help
if "%1"=="-h" goto show_help
if "%1"=="--check" goto mode_check

echo [ERROR] Unknown arg: %1
goto show_help

:show_help
echo ================================================
echo   Voice Assistant Launcher
echo ================================================
echo.
echo Usage: start.bat [OPTION]
echo   start.bat            Start Web UI (default)
echo   start.bat --check    Verify dependencies and exit
echo   start.bat --help     Show this help
echo.
echo After start, open http://127.0.0.1:8000 in browser.
echo.
exit /b 0

:mode_check
call :setup
.venv\Scripts\python.exe -m voice_assistant --check
exit /b

:mode_web
echo ================================================
echo   Voice Assistant - Web UI
echo ================================================
call :kill_port_8000
call :setup
echo [INFO] Starting Web UI on http://127.0.0.1:8000
.venv\Scripts\python.exe -m voice_assistant
exit /b

:kill_port_8000
echo [INFO] Checking port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo [INFO] Killing process on port 8000 (PID: %%a)
    taskkill /F /PID %%a >nul 2>&1
)
exit /b

:setup
echo.
where uv >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [ERROR] Failed to install uv. See https://astral.sh/uv
        exit /b 1
    )
)

if not exist ".venv" (
    echo [INFO] Creating venv...
    call uv venv .venv --python 3.12
    if errorlevel 1 (
        echo [ERROR] Failed to create venv
        exit /b 1
    )
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [INFO] Trying to install ffmpeg via winget...
    winget install ffmpeg --exact --id FFmpeg.FFmpeg --accept-source-urls --accept-package-agreements >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Failed to install ffmpeg via winget.
        echo [WARNING] Install manually from https://ffmpeg.org/download.html
    )
)

echo [INFO] Installing deps...
call .venv\Scripts\python.exe -m pip install -e ".[dev]" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Some dependencies may have failed to install.
)

if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [INFO] Created .env from .env.example - please edit and add API key
    )
)

echo [INFO] Ready
echo.
exit /b
