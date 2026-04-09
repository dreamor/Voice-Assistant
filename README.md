# Voice Assistant AI

中文语音助手 - 麦克风收音 → 语音识别 → 意图识别 → 路由执行 → 语音反馈

## 功能特性

- **语音识别 (ASR)**: 阿里云 DashScope Paraformer 实时识别
- **LLM 对话**: 阿里云百炼，支持对话理解和代码生成
- **语音合成 (TTS)**: Microsoft Edge-TTS，自然流畅
- **VAD 语音检测**: 自动检测说话开始/结束，无需手动操作
- **智能意图识别**: 自动判断用户意图，路由到对应执行器
- **Open Interpreter 集成**: 真正的 Open Interpreter 库，强大的电脑控制能力
- **对话上下文**: 支持多轮对话，保持上下文

## 项目结构

```
voice_assistant/
├── .env                     # 敏感配置（API Key 等）
├── .env.example             # 配置示例
├── config.yaml              # 应用配置
├── requirements.txt         # 依赖清单
├── voice_assistant_ai.py    # 主程序
├── config/                  # 配置模块
│   └── __init__.py
├── models/                  # 数据模型
│   ├── __init__.py
│   └── intent.py           # 意图数据类
├── executors/               # 执行器模块
│   ├── __init__.py
│   ├── base.py             # 执行器基类
│   ├── computer_executor.py # 电脑控制执行器
│   └── chat_executor.py    # 对话执行器
├── services/                # 服务模块
│   ├── __init__.py
│   └── router_service.py   # 命令路由器
├── interpreter_executor.py  # Open Interpreter 执行器
├── cloud_asr.py            # 语音识别模块
├── vad.py                  # 语音检测模块
├── tts.py                  # 语音合成模块
├── ai_client.py            # AI 对话模块
├── audio_player.py         # 音频播放模块
└── docs/                   # 文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

**必需配置：**
- `ASR_API_KEY` - 语音识别 API 密钥
- `LLM_API_KEY` - AI 对话 API 密钥

其他配置在 `config.yaml` 中调整。

### 3. 运行测试

```bash
pytest test_system.py -v
```

### 4. 启动

```bash
python voice_assistant_ai.py
```

## 使用说明

### 命令

| 按键 | 功能 |
|------|------|
| `Enter` | 开始录音（VAD 自动检测说话） |
| `C` | 清除对话历史 |
| `H` | 显示对话历史 |
| `I` | 切换 自动模式/AI 对话模式 |
| `Q` | 退出程序 |

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

llm:
  model: "kimi-k2.5"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  max_tokens: 2000
  temperature: 0.7

audio:
  sample_rate: 44100
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
| `Intent` | 意图数据类，LLM 与执行器之间的标准接口 |
| `BaseExecutor` | 执行器基类，定义标准接口 |
| `ComputerExecutor` | 电脑控制执行器（Open Interpreter） |
| `ChatExecutor` | 对话执行器（LLM 对话） |
| `CommandRouter` | 命令路由器，根据意图自动路由 |

### 意图类型

| 类型 | 说明 | 执行器 |
|------|------|--------|
| `COMPUTER_CONTROL` | 电脑操作 | ComputerExecutor |
| `ORDINARY_CHAT` | 普通对话 | ChatExecutor |
| `QUERY_ANSWER` | 问答查询 | ChatExecutor |

## 测试

```bash
pytest test_system.py -v
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