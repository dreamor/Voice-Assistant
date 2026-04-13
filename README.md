# Voice Assistant AI

中文语音助手 - 麦克风收音 → 语音识别 → 意图识别 → 路由执行 → 语音反馈

## 功能特性

- **语音识别 (ASR)**: 阿里云 DashScope Paraformer / 本地 FunASR 实时识别，支持中英文混合识别优化
- **LLM 对话**: 在线 API 对话生成
- **本地模型支持**: 使用 FunASR 运行 Paraformer-zh 本地语音识别，完全离线运行
- **语音合成 (TTS)**: Microsoft Edge-TTS，自然流畅
- **VAD 语音检测**: 自动检测说话开始/结束，无需手动操作
- **智能意图识别**: 自动判断用户意图，路由到对应执行器
- **Open Interpreter 集成**: 真正的 Open Interpreter 库，强大的电脑控制能力
- **对话上下文**: 支持多轮对话，保持上下文

## 项目结构

```
voice-assistant/
├── .env                     # 敏感配置（API Key 等）
├── .env.example             # 配置示例
├── config.yaml              # 应用配置
├── pyproject.toml           # 项目配置（uv）
├── run.py                   # 入口脚本
├── start.sh                 # 启动脚本
├── src/voice_assistant/     # 源代码包
│   ├── __init__.py
│   ├── main.py              # 主程序
│   ├── config/              # 配置模块
│   ├── audio/               # 音频模块
│   │   ├── vad.py           # 语音检测
│   │   ├── tts.py           # 语音合成
│   │   ├── player.py        # 音频播放
│   │   ├── cloud_asr.py     # 云端语音识别
│   │   └── funasr_asr.py    # 本地 FunASR 语音识别
│   ├── core/                # 核心模块
│   │   ├── ai_client.py     # AI 对话
│   │   ├── dependencies.py  # 依赖管理
│   │   └── asr_corrector.py # ASR 纠错
│   ├── executors/           # 执行器模块
│   │   ├── base.py          # 执行器基类
│   │   ├── chat.py          # 对话执行器
│   │   ├── computer.py      # 电脑控制执行器
│   │   └── interpreter.py   # Open Interpreter 执行器
│   ├── models/              # 数据模型
│   │   └── intent.py        # 意图数据类
│   ├── services/            # 服务模块
│   │   └── router.py        # 命令路由器
│   └── security/            # 安全模块
│       └── validation.py    # 输入验证
├── config/                  # 配置文件目录
│   └── hotwords.json        # 热词配置
├── model_weights/           # 本地模型文件（需下载）
├── tests/                   # 测试文件
└── docs/                    # 文档
```

## 快速开始

### 1. 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

### 2. 安装系统依赖

macOS 用户需要安装 ffmpeg（FunASR 音频加载依赖）：

```bash
brew install ffmpeg
```

Linux 用户：

```bash
sudo apt install ffmpeg
```

### 3. 安装 Python 依赖

```bash
# 使用启动脚本（推荐）
./start.sh

# 或手动安装
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev,local-asr]"
```

> **注意**: 需要 Python 3.10 或更高版本

### 4. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

**配置架构：**
- `.env` - 敏感信息（API Key）
- `config.yaml` - 非敏感配置（模型、参数等）

**必需配置：**
- `ASR_API_KEY` - 语音识别 API 密钥
- `LLM_API_KEY` - AI 对话 API 密钥（在线模式）

### 4. 运行测试

```bash
source .venv/bin/activate
pytest tests/ -v
```

### 5. 启动

```bash
# 使用启动脚本
./start.sh

# 或手动启动
source .venv/bin/activate
python run.py
```

## 使用说明

### 命令

| 按键 | 功能 |
|------|------|
| `Enter` | 开始录音（VAD 自动检测说话） |
| `C` | 清除对话历史 |
| `H` | 显示对话历史 |
| `I` | 切换 自动模式/AI 对话模式 |
| `A` | 切换 本地 FunASR / 云端 ASR 模式 |
| `Q` | 退出程序 |

### LLM 模式切换

按 `L` 键可在本地模型和在线 API 之间切换：

| 模式 | 模型 | 说明 |
|------|------|------|
| 在线 | kimi-k2.5 | 需要网络，API 调用 |
| 本地 | gemma-4-E2B-it | 离线运行，隐私保护 |

### 本地模型设置

使用 FunASR 本地语音识别（Paraformer-zh）：

1. 安装 FunASR 依赖：
```bash
pip install -e ".[local-asr]"
```

2. 首次启动时自动下载模型文件（约 2GB，存放在 `~/.cache/modelscope/hub/`）

3. 配置 `config.yaml`：
```yaml
asr:
  use_local: true  # true 使用本地 FunASR，false 使用云端 ASR
  local:
    enabled: true
    model_path: null  # null=自动下载，或指定本地路径
    device: "cpu"     # "cpu" 或 "cuda"
    vad_threshold: 0.5
```

### 工作流程

```
用户语音输入
    ↓
ASR 语音识别 → 文本
    ↓
意图识别（自动分类）
    │
    ├── 电脑操作（打开/关闭/创建/删除等）
    │       ↓
    │   ComputerExecutor (Open Interpreter)
    │       ↓
    │   解析意图 → 生成代码 → 执行 → 语音反馈
    │
    └── 普通对话/问答
            ↓
        ChatExecutor
            ↓
        LLM 对话生成 → 语音反馈
```

### 模式说明

**自动模式** (默认):
- 自动识别用户意图
- 电脑操作 → Open Interpreter 执行
- 普通对话 → LLM 对话生成

**AI 对话模式**:
- 强制使用 LLM 对话
- 适用于纯聊天场景

## 配置说明

### config.yaml

应用配置在 `config.yaml` 中：

```yaml
app:
  name: "Voice Assistant"
  version: "2.0.0"

asr:
  model: "paraformer-realtime-v2"
  base_url: "https://dashscope.aliyuncs.com/api/v1"
  language_hints: ["zh", "en"]  # 中英文混合识别
  disfluency_removal_enabled: true  # 过滤语气词

llm:
  model: "kimi-k2.5"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  max_tokens: 2000
  temperature: 0.7
  use_local: false  # 本地模型开关
  local:
    model_path: "model_weights/gemma-4-E2B-it.litertlm"
    model_name: "gemma-4-E2B-it"

audio:
  sample_rate: 16000  # ASR 标准采样率
  edge_tts_voice: "zh-CN-XiaoxiaoNeural"

vad:
  threshold: 0.02
  silence_timeout: 1.5
  min_speech: 0.3
  max_recording: 30

interpreter:
  auto_run: true
  verbose: false
```

### .env

敏感信息在 `.env` 中：

```ini
ASR_API_KEY=your-asr-api-key
LLM_API_KEY=your-llm-api-key
```

## 架构说明

### 核心模块

| 模块 | 职责 |
|------|------|
| `voice_assistant.models.intent` | 意图数据类，LLM 与执行器之间的标准接口 |
| `voice_assistant.executors.base` | 执行器基类，定义标准接口 |
| `voice_assistant.executors.computer` | 电脑控制执行器（Open Interpreter） |
| `voice_assistant.executors.chat` | 对话执行器（LLM 对话） |
| `voice_assistant.services.router` | 命令路由器，根据意图自动路由 |
| `voice_assistant.core.local_llm` | 本地 LLM 客户端（LiteRT-LM） |
| `voice_assistant.core.model_manager` | 模型管理器，支持模型自动切换和故障转移 |

### 模型自动切换

当主模型不可用时（如限流、余额不足、服务异常），系统会自动切换到备用模型：

```python
from voice_assistant.core import model_manager, get_model_queue_info

# 查看当前模型队列
info = get_model_queue_info()
print(f"当前模型: {info['current_model']}")
print(f"备用模型: {info['models'][1:]}")

# 获取所有可用模型
models = model_manager.list_available_models()
for m in models:
    print(f"- {m['id']}")
```

特性：
- 自动获取阿里云百炼平台所有可用模型
- 按优先级构建备用模型队列（qwen-plus > qwen-turbo > qwen-max）
- 智能错误判断，输入问题不切换模型
- 运行时自动切换，用户无感知

### 意图类型

| 类型 | 说明 | 执行器 |
|------|------|--------|
| `COMPUTER_CONTROL` | 电脑操作 | ComputerExecutor |
| `ORDINARY_CHAT` | 普通对话 | ChatExecutor |
| `QUERY_ANSWER` | 问答查询 | ChatExecutor |

## 测试

```bash
source .venv/bin/activate
pytest tests/ -v
```

测试覆盖：依赖包、配置读取、API 连接、各模块功能

## 文档

详见 `docs/` 目录：
- [架构文档](docs/ARCHITECTURE.md) - 系统架构
- [模块说明](docs/MODULES.md) - 各模块详解
- [配置说明](docs/CONFIG.md) - 配置参数
- [开发指南](docs/DEVELOPMENT.md) - 开发指南
- [API 参考](docs/API.md) - 接口文档

## License

MIT