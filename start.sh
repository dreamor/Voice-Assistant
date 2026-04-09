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

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}错误: 需要 Python $REQUIRED_VERSION 或更高版本${NC}"
    echo -e "当前版本: Python $PYTHON_VERSION"
    echo -e "请安装 Python 3.10+ 后重试"
    exit 1
fi

echo -e "${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"

# 创建虚拟环境（如果不存在）
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    uv venv --python 3.12
fi

# 安装依赖
echo -e "${YELLOW}检查依赖...${NC}"
uv pip install -e ".[dev,local-llm]"

# 检查环境变量
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}警告: .env 文件不存在${NC}"
    echo -e "请复制 .env.example 并填入 API 密钥"
fi

# 检查本地模型
if [ -f "model_weights/gemma-4-E2B-it.litertlm" ]; then
    echo -e "${GREEN}✓ 本地模型已就绪${NC}"
else
    echo -e "${YELLOW}提示: 本地模型未安装，将使用在线模式${NC}"
    echo -e "下载模型: 参考 docs/CONFIG.md"
fi

echo "================================"
echo -e "${GREEN}启动 Voice Assistant...${NC}"
echo ""

# 启动应用
source .venv/bin/activate
python voice_assistant_ai.py