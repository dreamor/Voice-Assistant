#!/bin/bash
# Voice Assistant 启动脚本
# 使用 uv 管理虚拟环境和依赖
#
# 用法:
#   ./start.sh              启动命令行版本（默认）
#   ./start.sh --web        启动 Web UI 版本
#   ./start.sh --both       同时启动命令行和 Web UI
#   ./start.sh --help       显示帮助

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_help() {
    echo -e "${GREEN}Voice Assistant 启动脚本${NC}"
    echo "================================"
    echo ""
    echo "用法:"
    echo "  ./start.sh              启动命令行版本（默认）"
    echo "  ./start.sh --web        启动 Web UI 版本"
    echo "  ./start.sh --both       同时启动命令行和 Web UI"
    echo "  ./start.sh --help       显示此帮助"
    echo ""
    echo "启动模式:"
    echo "  --web     启动 Web UI（浏览器访问 http://127.0.0.1:8000）"
    echo "  --both    同时启动命令行和 Web UI"
    echo ""
}

# 默认启动模式
MODE="cli"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --web)
            MODE="web"
            shift
            ;;
        --both)
            MODE="both"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            echo "使用 ./start.sh --help 查看帮助"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}Voice Assistant 启动脚本${NC}"
echo "================================"

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv 未安装，正在安装...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 使用 uv 管理 Python，自动下载所需版本
echo -e "${GREEN}✓ 使用 uv 管理 Python 环境${NC}"
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}创建虚拟环境（uv 将自动下载 Python 3.12）...${NC}"
    uv venv --python 3.12
    echo -e "${GREEN}✓ 虚拟环境已创建${NC}"
fi

# 验证 venv 中的 Python 版本
VENV_PYTHON=$(.venv/bin/python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python 版本: $VENV_PYTHON${NC}"

# 检查 FunASR 本地 ASR 配置
USE_LOCAL_ASR=false
if [ -d "$HOME/.cache/modelscope/hub/models/iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch" ]; then
    USE_LOCAL_ASR=true
    echo -e "${GREEN}✓ 本地 ASR 模型已就绪${NC}"
elif grep -q "use_local:\s*true" config.yaml 2>/dev/null; then
    USE_LOCAL_ASR=true
    echo -e "${GREEN}✓ 本地 ASR 配置已启用${NC}"
else
    echo -e "${YELLOW}提示: 本地 ASR 未配置，将使用云端 ASR${NC}"
    echo -e "设置 config.yaml 中 asr.use_local: true 启用本地 ASR"
fi

# 安装依赖
echo -e "${YELLOW}检查依赖...${NC}"
if [ "$USE_LOCAL_ASR" = true ]; then
    uv pip install -e ".[dev,local-asr]"
else
    uv pip install -e ".[dev]"
fi

# 检查 ffmpeg 是否安装（FunASR 依赖）
if command -v ffmpeg &> /dev/null; then
    echo -e "${GREEN}✓ ffmpeg 已就绪${NC}"
else
    echo -e "${YELLOW}⚠ ffmpeg 未安装（本地 ASR 依赖）${NC}"
    echo -e "  macOS: brew install ffmpeg"
    echo -e "  Linux: sudo apt install ffmpeg"
fi

echo "================================"

# 激活虚拟环境
source .venv/bin/activate

# 根据模式启动
case $MODE in
    cli)
        echo -e "${GREEN}启动命令行版本...${NC}"
        echo ""
        python -m voice_assistant
        ;;
    web)
        echo -e "${GREEN}启动 Web UI 版本...${NC}"
        echo -e "${BLUE}📱 请在浏览器中访问: http://127.0.0.1:8000${NC}"
        echo ""
        python -m voice_assistant --web
        ;;
    both)
        echo -e "${GREEN}启动命令行和 Web UI...${NC}"
        echo -e "${BLUE}📱 Web UI: http://127.0.0.1:8000${NC}"
        echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
        echo ""
        # 后台启动 Web UI
        python -m voice_assistant --web &
        WEB_PID=$!
        # 前台启动命令行
        python -m voice_assistant
        # 清理后台进程
        kill $WEB_PID 2>/dev/null || true
        ;;
esac
