#!/bin/bash
# Voice Assistant launcher
# Uses uv for Python environment

set -e

ARG="$1"

show_help() {
    echo "================================"
    echo "  Voice Assistant Launcher"
    echo "================================"
    echo ""
    echo "Usage: start.sh [MODE]"
    echo "  start.sh           - CLI mode"
    echo "  start.sh --web     - Web UI"
    echo "  start.sh --both   - CLI + Web UI"
    echo "  start.sh --help    - This help"
    echo ""
}

case "$ARG" in
    --help|-h) show_help; exit 0 ;;
    --web) MODE="web" ;;
    --both) MODE="both" ;;
    "") MODE="cli" ;;
    *) echo "[ERROR] Unknown: $ARG"; exit 1 ;;
esac

echo "================================"
echo "  Voice Assistant"
echo "================================"
echo.

# Check uv
if ! command -v uv &> /dev/null; then
    echo "[INFO] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Create venv
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating venv..."
    uv venv --python 3.12
fi

# Check ffmpeg (required for FunASR)
if ! command -v ffmpeg &> /dev/null; then
    echo "[INFO] Installing ffmpeg..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    elif command -v apt &> /dev/null; then
        sudo apt update && sudo apt install -y ffmpeg
    fi
fi

# Always install FunASR for local ASR option
echo "[INFO] Installing dependencies (with FunASR)..."
uv pip install -e ".[dev,local-asr]" 2>/dev/null || true

# Copy .env
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
fi

echo "[INFO] Ready"
echo.

# Launch
case "$MODE" in
    web)
        echo "Starting Web UI..."
        .venv/bin/python -m voice_assistant --web
        ;;
    both)
        echo "Starting both modes..."
        .venv/bin/python -m voice_assistant --web &
        .venv/bin/python -m voice_assistant
        ;;
    *)
        echo "Starting CLI..."
        .venv/bin/python -m voice_assistant
        ;;
esac