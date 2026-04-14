@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

REM 解析参数
set "MODE=cli"
set "SHOW_HELP=false"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--web" (
    set "MODE=web"
    shift
    goto parse_args
)
if /i "%~1"=="--both" (
    set "MODE=both"
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    set "SHOW_HELP=true"
    shift
    goto parse_args
)
if /i "%~1"=="-h" (
    set "SHOW_HELP=true"
    shift
    goto parse_args
)
echo [ERROR] Unknown argument: %~1
echo Use --help for usage information
exit /b 1

:args_done

REM 显示帮助
if "%SHOW_HELP%"=="true" (
    echo ================================================
    echo   Voice Assistant Launcher (Windows)
    echo ================================================
    echo.
    echo Usage:
    echo   start.bat              启动命令行版本（默认）
    echo   start.bat --web        启动 Web UI 版本
    echo   start.bat --both       同时启动命令行和 Web UI
    echo   start.bat --help       显示此帮助
    echo.
    echo 启动模式:
    echo   --web     启动 Web UI（浏览器访问 http://127.0.0.1:8000）
    echo   --both    同时启动命令行和 Web UI
    echo.
    exit /b 0
)

echo ================================================
echo   Voice Assistant Launcher (Windows)
echo ================================================
echo.

REM 检查 uv 是否安装
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] uv not found, installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
)

REM 使用 uv 创建虚拟环境（自动下载 Python）
if not exist ".venv" (
    echo [INFO] Creating virtual environment with uv...
    uv venv --python 3.12
)

REM 激活虚拟环境获取 Python 版本
for /f "delims=" %%i in ('.venv\Scripts\python.exe --version 2^>nul') do set PYTHON_VERSION=%%i
echo [INFO] Python version: !PYTHON_VERSION!

REM 检查 FunASR 本地 ASR 配置
set USE_LOCAL_ASR=false
if exist "%USERPROFILE%\.cache\modelscope\hub\models\iic\speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch" (
    set USE_LOCAL_ASR=true
    echo [INFO] Local ASR model ready
) else (
    findstr /C:"use_local: true" config.yaml >nul 2>&1
    if !errorlevel! equ 0 (
        set USE_LOCAL_ASR=true
        echo [INFO] Local ASR enabled in config
    ) else (
        echo [INFO] Local ASR not configured, using cloud ASR
    )
)

REM 安装依赖
echo [INFO] Installing dependencies...
if "!USE_LOCAL_ASR!"=="true" (
    uv pip install -e ".[dev,local-asr]"
) else (
    uv pip install -e ".[dev]"
)

REM 检查 ffmpeg 是否安装（FunASR 依赖）
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] ffmpeg not found (required for local ASR)
    echo [INFO] Install ffmpeg: winget install ffmpeg
) else (
    echo [INFO] ffmpeg ready
)

REM 复制 .env 示例文件（如不存在）
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Copying .env.example to .env
        copy .env.example .env
    )
)

echo.
echo ================================================

REM 根据模式启动
if "%MODE%"=="web" (
    echo   Starting Voice Assistant Web UI...
    echo ================================================
    echo.
    echo [INFO] Please visit: http://127.0.0.1:8000
    echo.
    .venv\Scripts\python.exe -m voice_assistant --web
) else if "%MODE%"=="both" (
    echo   Starting Voice Assistant (Both modes)...
    echo ================================================
    echo.
    echo [INFO] Web UI: http://127.0.0.1:8000
    echo [INFO] Press Ctrl+C to stop all services
    echo.
    REM 后台启动 Web UI
    start /b "" .venv\Scripts\python.exe -m voice_assistant --web
    REM 前台启动命令行
    .venv\Scripts\python.exe -m voice_assistant
    REM 关闭后台进程
    taskkill /F /IM python.exe >nul 2>&1
) else (
    echo   Starting Voice Assistant (CLI)...
    echo ================================================
    echo.
    .venv\Scripts\python.exe -m voice_assistant
)

pause
