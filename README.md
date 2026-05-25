# Voice Assistant

[![CI](https://github.com/dreamor/Voice-Assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/dreamor/Voice-Assistant/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

浏览器原生中文语音助手 — 录音 → 实时 ASR → Agent Loop → 流式 TTS。

## 特性

- **Web UI** · FastAPI + WebSocket + ES Module，无需原生客户端
- **多 Provider** · DashScope / OpenAI / Anthropic / DeepSeek，Web 界面一键添加自定义 OpenAI 兼容端点
- **流式输出** · LLM token 级流式 + 分句 TTS，边生成边播放
- **Agent Loop** · function calling + tool 注册表 + 分级安全守卫（auto / confirm / double-confirm / blocked）
- **MCP & Skill** · 外部 MCP server（stdio/sse/http）接入 ToolRegistry；SKILL.md 风格能力包按关键词触发，详见 [MCP_SKILL](docs/MCP_SKILL.md)
- **Python 代码兜底** · 内置 `run_python_code` tool，LLM 可在没有专用工具时执行短脚本（受确认与超时保护）
- **ASR** · DashScope Paraformer，或可选本地 FunASR Paraformer-zh 离线运行
- **模型自动切换** · 主模型失败时在当前 Provider 的 models 内按顺序降级
- **历史管理** · SQLite 持久化，支持批量选择 / 全选 / 删除
- **平台工具** · macOS / Windows 自动加载对应原生操作
## 一键启动

```bash
# macOS
./start.sh              # 自动装 uv / ffmpeg / 依赖，拉起 Web UI

# Windows
start.bat

# 其他选项
./start.sh --check      # 仅检查依赖
./start.sh --help
```

首次运行会自动从 `.env.example` 复制出 `.env`，填入任一 Provider 的 API Key 后重启即可。浏览器打开 <http://127.0.0.1:8000>。

## 手动启动

```bash
# 1. 安装依赖
brew install ffmpeg                                   # macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. 配置 API Key（任一 Provider）
cp .env.example .env && $EDITOR .env

# 3. 启动
python -m voice_assistant
# 浏览器打开 http://127.0.0.1:8000
```

> Python 3.10+。完整说明见 [QUICKSTART](docs/QUICKSTART.md)。

## 使用

| 操作 | 说明 |
|------|------|
| 🎙️ 麦克风 | 浏览器 VAD 自动检测静音结束 |
| 💬 文本框 | 键盘输入，支持 IME |
| ⊕ | 新对话 |
| ☑ | 批量选择（全选 / 删除选中） |
| ⚙ | 配置页（Provider 切换、添加、参数调整） |

### 添加自定义 Provider

⚙ → **添加 Provider** → 填入 ID / Base URL / API Key → 回车追加模型，或「从 API 获取模型」自动拉取。持久化到 `config/custom_providers.yaml`。

## 架构

```
浏览器 ──WS──▶ FastAPI ──▶ VoiceSession ──▶ Agent Loop
                                            ├─ LLM (litellm, stream + tools)
                                            ├─ 安全守卫
                                            └─ Tool Registry
                                                  ↓
                                            TTS stream ──▶ StreamingAudioPlayer
```

详见 [ARCHITECTURE](docs/ARCHITECTURE.md)。

## 配置

```yaml
# config.yaml 摘要
llm:
  max_tokens: 2000
  temperature: 0.7
asr:
  model: "paraformer-realtime-v2"
  use_local: false                 # 可切换到 FunASR
agent:
  max_iterations: 5
providers:
  # 内置：dashscope / openai / anthropic / deepseek
  # 自定义 provider 写入 config/custom_providers.yaml
# 当前 provider 由 .env 的 LLM_API_KEY 序号决定（1 = 第一个 provider）
```

完整说明见 [CONFIG](docs/CONFIG.md)。

## 开发

```bash
pytest tests/ -v             # 测试（512 用例）
ruff check src/ tests/       # lint
pyright src/                 # type check
python scripts/check_env.py  # 环境自检（Python / 依赖 / .env / 麦克风）
```

> 启用 ASR 热词：`python scripts/register_hotwords.py` → 把输出的 `vocabulary_id` 填入 `config.yaml`。详见 [CONFIG](docs/CONFIG.md)。

更多见 [DEVELOPMENT](docs/DEVELOPMENT.md)。

## 文档

- [QUICKSTART](docs/QUICKSTART.md) · 5 分钟上手
- [ARCHITECTURE](docs/ARCHITECTURE.md) · 系统架构
- [MODULES](docs/MODULES.md) · 模块详解
- [CONFIG](docs/CONFIG.md) · 配置参数
- [API](docs/API.md) · REST + WebSocket
- [MCP & Skill](docs/MCP_SKILL.md) · 接入外部 MCP server 与编写 Skill
- [DEVELOPMENT](docs/DEVELOPMENT.md) · 贡献指南

## License

MIT
