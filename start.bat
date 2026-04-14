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
call :setup
.venv\Scripts\python.exe -m voice_assistant --web
exit /b

:mode_both
echo ================================================
echo   Voice Assistant - Both
echo ================================================
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

:setup
echo.
where uv 2>nul
if errorlevel 1 (
    echo [INFO] Installing uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)

if not exist ".venv" (
    echo [INFO] Creating venv...
    uv venv --python 3.12
)

where ffmpeg 2>nul
if errorlevel 1 (
    echo [INFO] Installing ffmpeg...
    winget install ffmpeg -e --accept-source-urls --accept-package-agreements >nul 2>&1
)

echo [INFO] Installing deps...
uv pip install -e ".[dev,local-asr]" 2>nul

if not exist ".env" (
    if exist ".env.example" copy .env.example .env >nul
)

echo [INFO] Ready
echo.
exit /b