@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

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

REM 检查本地模型
set USE_LOCAL_LLM=false
if exist "model_weights\gemma-4-E2B-it.litertlm" (
    set USE_LOCAL_LLM=true
    echo [INFO] Local model ready
) else (
    findstr /C:"use_local: true" config.yaml >nul 2>&1
    if !errorlevel! equ 0 (
        set USE_LOCAL_LLM=true
        echo [INFO] Local model enabled in config
    ) else (
        echo [INFO] Local model not installed, using online mode
    )
)

REM 安装依赖
echo [INFO] Installing dependencies...
if "!USE_LOCAL_LLM!"=="true" (
    uv pip install -e ".[dev,local-llm]"
) else (
    uv pip install -e ".[dev]"
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
echo   Starting Voice Assistant...
echo ================================================
echo.

REM 启动应用
.venv\Scripts\python.exe run.py

pause