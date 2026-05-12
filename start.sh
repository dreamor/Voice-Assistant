#!/bin/bash
# Voice Assistant launcher (Web only)

set -e

cd "$(dirname "$0")"

show_help() {
    cat <<EOF
================================
  Voice Assistant Launcher
================================

Usage: start.sh [OPTION]
  start.sh            Start Web UI (default)
  start.sh --check    Verify dependencies and exit
  start.sh --help     Show this help

After start, open http://127.0.0.1:8000 in browser.
EOF
}

ARG="$1"
case "$ARG" in
    --help|-h) show_help; exit 0 ;;
    --check)   MODE="check" ;;
    "")        MODE="web" ;;
    *) echo "[ERROR] Unknown arg: $ARG"; show_help; exit 1 ;;
esac

echo "================================"
echo "  Voice Assistant"
echo "================================"
echo

# Check uv
if ! command -v uv >/dev/null 2>&1; then
    echo "[INFO] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create venv
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating venv..."
    uv venv .venv --python 3.12
fi

# Check ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[WARNING] ffmpeg not found."
    if command -v brew >/dev/null 2>&1; then
        echo "[INFO] Installing ffmpeg via brew..."
        brew install ffmpeg || true
    elif command -v apt-get >/dev/null 2>&1; then
        echo "[INFO] Installing ffmpeg via apt..."
        sudo apt-get install -y ffmpeg || true
    else
        echo "[WARNING] Please install ffmpeg manually."
    fi
fi

# Install deps (idempotent)
echo "[INFO] Installing deps..."
.venv/bin/python -m pip install -e ".[dev]" >/dev/null 2>&1 || \
    echo "[WARNING] Some dependencies may have failed to install."

# Copy .env if missing
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "[INFO] Created .env from .env.example - please edit and add API key"
fi

kill_port_8000() {
    pid=$(lsof -ti:8000 2>/dev/null || true)
    if [ -n "$pid" ]; then
        echo "[INFO] Killing existing process on port 8000 (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
    fi
}

echo "[INFO] Ready"
echo

case "$MODE" in
    check)
        .venv/bin/python -m voice_assistant --check
        ;;
    web)
        kill_port_8000
        echo "[INFO] Starting Web UI on http://127.0.0.1:8000"
        .venv/bin/python -m voice_assistant
        ;;
esac
