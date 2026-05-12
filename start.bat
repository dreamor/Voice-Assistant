@echo off
chcp 65001 >nul 2>&1
setlocal

cd /d "%~dp0"

if "%1"=="" goto mode_cli
if "%1"=="--help" goto show_help
if "%1"=="-h" goto show_help
if "%1"=="--web" goto mode_web
if "%1"=="--both" goto mode_both

echo [ERROR] Unknown arg: %1
exit /b 1

:show_help
echo ================================================
echo   Voice Assistant Launcher
echo ================================================
echo.
echo Usage: start.bat [MODE]
echo   start.bat           - CLI mode
echo   start.bat --web     - Web UI
echo   start.bat --both    - CLI + Web UI
echo   start.bat --help    - This help
echo.
exit /b 0

:mode_web
echo ================================================
echo   Voice Assistant - Web UI
echo ================================================
call :kill_port_8000
call :setup
.venv\Scripts\python.exe -m voice_assistant --web
exit /b

:mode_both
echo ================================================
echo   Voice Assistant - Both
echo ================================================
call :kill_port_8000
call :setup
start "" .venv\Scripts\python.exe -m voice_assistant --web
.venv\Scripts\python.exe -m voice_assistant
exit /b

:mode_cli
echo ================================================
echo   Voice Assistant - CLI
echo ================================================
call :setup
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
where uv 2>nul
if errorlevel 1 (
    echo [INFO] Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [ERROR] Failed to install uv. Please install manually from https://astral.sh/uv
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

where ffmpeg 2>nul
if errorlevel 1 (
    echo [INFO] Trying to install ffmpeg...
    winget install ffmpeg --exact --id FFmpeg.FFmpeg --accept-source-urls --accept-package-agreements >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Failed to install ffmpeg via winget.
        echo [WARNING] Please install ffmpeg manually from https://ffmpeg.org/download.html
    )
)

echo [INFO] Installing deps...
call .venv\Scripts\python.exe -m pip install -e ".[dev,local-asr]" 2>nul
if errorlevel 1 (
    echo [WARNING] Some dependencies may have failed to install.
)

if not exist ".env" (
    if exist ".env.example" copy .env.example .env >nul
)

echo [INFO] Ready
echo.
exit /b