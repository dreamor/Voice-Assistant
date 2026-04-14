#!/bin/bash
# Voice Assistant 启动脚本
# 使用 uv 管理虚拟环境和依赖

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
echo -e "${GREEN}启动 Voice Assistant...${NC}"
echo ""

# 启动应用
source .venv/bin/activate
python run.py
