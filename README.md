# Voice Assistant AI

纯 Web 的中文语音助手 — 浏览器录音 → 语音识别 → Agent Loop → 流式语音反馈。

## 功能特性

- **🌐 Web UI**: 简洁现代的浏览器界面，支持录音、流式对话、批量管理历史、Provider 配置
- **多 Provider**: 内置 DashScope / OpenAI / Anthropic / DeepSeek，支持 Web 界面新增自定义 Provider（base_url + api_key + 模型列表）
- **流式输出**: LLM token 级流式 + 分块 TTS 合成，逐句播放
- **语音识别 (ASR)**: 阿里云 DashScope Paraformer 实时识别，支持中英文混合，可选本地 FunASR 离线运行
- **Agent Loop**: LLM function calling → tool 执行 → 结果回传 → 循环，支持多轮工具调用
- **语音合成 (TTS)**: Microsoft Edge-TTS，自然流畅
- **Tool 系统**: 内置通用工具（文件、剪贴板、屏幕、输入）+ 平台特定工具，可扩展
- **安全确认机制**: 分级拦截（自动 / 确认 / 二次确认 / 阻止）
- **Open Interpreter 集成**: 无匹配 tool 时回退到 Open Interpreter
- **SQLite 对话历史**: 持久化对话记录，Web UI 支持单条 / 批量删除
- **模型自动切换**: 主模型故障时自动切换到备用模型
- **平台检测**: 自动识别操作系统，加载对应平台工具

## 项目结构

```
voice-assistant/
├── .env                      # 敏感配置（API Key）
├── .env.example              # 配置示例
├── config.yaml               # 应用配置 + 内置 providers
├── config/
│   ├── hotwords.json         # 热词配置
│   └── custom_providers.yaml # 用户自定义 Provider（运行时由 Web UI 写入）
├── pyproject.toml            # 项目配置（uv）
├── web_ui.py                 # FastAPI 后端 + WebSocket
├── web_static/               # Web UI 前端
│   ├── index.html
│   ├── style.css
│   └── js/
│       ├── app.js            # 入口
│       ├── state.js          # 全局状态
│       ├── api.js            # REST 客户端
│       ├── ws.js             # WebSocket
│       ├── audio.js          # 录音 / 播放 / StreamingAudioPlayer
│       ├── ui.js             # 列表、消息、批量选择
│       ├── config.js         # 配置页面（Provider 管理）
│       └── utils.js
├── src/voice_assistant/
│   ├── __main__.py           # 入口：启动 Web UI
│   ├── db.py                 # SQLite 对话历史
│   ├── config/               # 配置加载 + 自定义 Provider 持久化
│   ├── audio/
│   │   ├── cloud_asr.py      # 云端 ASR
│   │   ├── funasr_asr.py     # 本地 FunASR
│   │   └── tts.py            # TTS Provider
│   ├── core/
│   │   ├── session.py        # VoiceSession（流式生成、历史）
│   │   ├── ai_client.py
│   │   ├── model_manager.py  # 模型故障转移
│   │   └── dependencies.py
│   ├── agent/
│   │   ├── orchestrator.py   # Agent 循环
│   │   └── llm_client.py     # Function Calling 通信层
│   ├── executors/            # 对话 / 电脑控制 / Open Interpreter
│   ├── tools/                # Tool 注册表 + 通用 / 平台工具
│   ├── security/             # 输入验证 + 安全守卫
│   └── platform/             # 平台检测
├── data/
│   └── web_ui.db             # SQLite 数据库
├── tests/
└── docs/
```

## 快速开始

### 1. 安装 uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

### 2. 安装系统依赖

macOS：

```bash
brew install ffmpeg
```

Linux：

```bash
sudo apt install ffmpeg
```

### 3. 安装 Python 依赖

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"

# 可选：本地 ASR
uv pip install -e ".[local-asr]"
```

> 需要 Python 3.10 或更高版本。

### 4. 配置

```bash
cp .env.example .env
# 编辑 .env 填入 API Key
```

**配置架构**

- `.env` — 敏感信息（API Key）
- `config.yaml` — 非敏感配置（模型、参数、内置 Provider）
- `config/custom_providers.yaml` — Web UI 写入的自定义 Provider（自动生成）

**最少配置**：任一 Provider 的 API Key，例如 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY`。也可以启动后在 Web UI 配置页添加。

### 5. 运行测试

```bash
source .venv/bin/activate
pytest tests/ -v
```

### 6. 启动

```bash
source .venv/bin/activate
python -m voice_assistant
```

浏览器打开 **http://127.0.0.1:8000** 即可使用。

## 使用说明

### Web UI 能力

- 🎙️ **录音输入** — 点击麦克风录音，VAD 自动检测说话结束，实时 ASR
- 💬 **文字输入** — 键盘输入，支持 IME
- 🔄 **流式响应** — token 级流式显示，分块 TTS 逐句播放
- 📜 **对话历史** — 左侧列表，支持单条删除 / 批量选择 / 全选 / 清空
- ⚙️ **配置页** — 切换 Provider 与模型、添加自定义 Provider、调整 temperature / max_tokens

### 添加自定义 Provider

点击左下角⚙️ → 「添加 Provider」：

| 字段 | 说明 |
|------|------|
| Provider ID | 字母 / 数字 / `-` / `_`（不可与内置 ID 冲突） |
| 名称 | 显示名称 |
| Base URL | OpenAI 兼容端点，如 `https://api.deepseek.com/v1` |
| API Key | 将写入 `.env`（变量名自动由 ID 推导） |
| LiteLLM Prefix | `openai` / `anthropic` 等 |
| 模型列表 | 回车逐个添加，或点击「从 API 获取模型」自动拉取 |

创建后立刻写入 `config/custom_providers.yaml` 并出现在 Provider 列表。

### 本地 ASR 设置

```yaml
# config.yaml
asr:
  use_local: true
  local:
    enabled: true
    model_path: null   # null = 自动下载到 ~/.cache/modelscope/hub/
    device: "cpu"      # 或 "cuda"
    vad_threshold: 0.5
```

首次启动自动下载模型文件（约 2GB）。

### 工作流程

```
浏览器录音 → WebSocket 上传
    ↓
ASR 识别 → 文本
    ↓
意图识别（自动分类）
    ├─ 电脑操作 → Agent Loop（LLM function calling）
    │     └─ 安全守卫 → Tool 执行 → 结果回传 → 循环
    └─ 普通对话 → ChatExecutor（LLM 流式对话）
    ↓
流式 TTS 合成 → 分块推送 → 浏览器逐句播放
```

## 配置说明

### config.yaml

```yaml
app:
  name: "Voice Assistant"
  version: "2.0.0"

asr:
  model: "paraformer-realtime-v2"
  base_url: "https://dashscope.aliyuncs.com/api/v1"
  language_hints: ["zh", "en"]
  disfluency_removal_enabled: true
  max_sentence_silence: 1200
  use_local: false
  local:
    enabled: false
    model_path: null
    device: "cpu"
    vad_threshold: 0.5
  hotwords:
    enabled: false
    config_file: "config/hotwords.json"

llm:
  model: "qwen-plus-latest"
  max_tokens: 2000
  temperature: 0.7

audio:
  sample_rate: 16000
  edge_tts_voice: "zh-CN-XiaoxiaoNeural"

vad:
  threshold: 0.02
  silence_timeout: 1.5
  min_speech: 0.3
  max_recording: 30

interpreter:
  auto_run: true
  verbose: false

conversation_history:
  enabled: true
  max_turns: 50

logging:
  level: "INFO"
  file: null

intent:
  model: "qwen-turbo"
  timeout: 5

agent:
  max_iterations: 5
  confirmation_timeout: 60
  fallback_to_interpreter: true

tools:
  blocked: []
  overrides: []

providers:
  dashscope:
    name: "阿里云 DashScope"
    litellm_prefix: "openai"
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key_env: "LLM_API_KEY"
    models:
      - id: "qwen-plus-latest"
        name: "Qwen Plus"
  openai:
    name: "OpenAI"
    litellm_prefix: "openai"
    base_url: null
    api_key_env: "OPENAI_API_KEY"
    models:
      - id: "gpt-4o-mini"
        name: "GPT-4o Mini"
  # anthropic / deepseek ...
```

### .env

```ini
DASHSCOPE_API_KEY=your-dashscope-api-key
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

## 架构说明

### 核心模块

| 模块 | 职责 |
|------|------|
| `voice_assistant.core.session` | VoiceSession，Web UI 会话逻辑与流式生成 |
| `voice_assistant.core.model_manager` | 模型管理器，支持模型自动切换与 Provider 切换 |
| `voice_assistant.core.ai_client` | AI 对话客户端，流式调用 |
| `voice_assistant.agent.orchestrator` | Agent 循环，function calling → tool → 循环 |
| `voice_assistant.agent.llm_client` | Function Calling 通信层（基于 litellm） |
| `voice_assistant.executors.*` | 对话 / 电脑控制 / Open Interpreter 执行器 |
| `voice_assistant.services.router` | 根据意图路由到对应执行器 |
| `voice_assistant.security.safe_guard` | 工具调用分级拦截 |
| `voice_assistant.tools.registry` | 工具注册表 |
| `voice_assistant.db` | SQLite 对话历史 |
| `voice_assistant.config` | 配置加载 + `custom_providers.yaml` 读写 |

### Agent Loop

```
用户输入 → 意图识别 → Agent Loop
                      ├─ LLM function calling（流式）
                      ├─ 安全守卫检查
                      │     ├─ 自动通过
                      │     ├─ 需确认
                      │     ├─ 二次确认
                      │     └─ 阻止
                      ├─ Tool 执行 → 结果回传 LLM
                      ├─ 继续调用 or 返回最终回复
                      └─ 无匹配 tool → 回退到 Open Interpreter
```

### 模型自动切换

主模型不可用时（限流、余额不足、服务异常）自动切换到备用模型。智能错误判断：HTTP 429/500 触发切换，HTTP 400（输入问题）不切换。

### 意图类型

| 类型 | 执行器 |
|------|--------|
| `COMPUTER_CONTROL` | ComputerExecutor |
| `ORDINARY_CHAT` | ChatExecutor |
| `QUERY_ANSWER` | ChatExecutor |

## 测试

```bash
source .venv/bin/activate
pytest tests/ -v
```

## 文档

- [架构文档](docs/ARCHITECTURE.md)
- [模块说明](docs/MODULES.md)
- [配置说明](docs/CONFIG.md)
- [开发指南](docs/DEVELOPMENT.md)
- [API 参考](docs/API.md)

## License

MIT
