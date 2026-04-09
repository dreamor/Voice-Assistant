# Voice Assistant AI

中文语音助手 - 麦克风收音 → 语音识别 → AI处理 → 语音合成 → 扬声器播放

## 功能特性

- **语音识别 (ASR)**: 阿里云 DashScope Paraformer 实时识别
- **LLM 对话**: 阿里云百炼，支持对话理解和代码生成
- **语音合成 (TTS)**: Microsoft Edge-TTS，自然流畅
- **VAD 语音检测**: 自动检测说话开始/结束，无需手动操作
- **智能模式切换**:
  - **Interpreter 模式**: 检测电脑操作指令，执行 Python/Bash 代码
  - **AI 模式**: 纯对话模式，LLM 生成自然语言回复
- **对话上下文**: 支持多轮对话，保持上下文

## 项目结构

```
voice_assistant/
├── .env                     # 配置文件
├── .env.sample             # 配置示例
├── requirements.txt        # 依赖清单
├── voice_assistant_ai.py   # 主程序
├── cloud_asr.py            # 语音识别模块
├── vad.py                  # 语音检测模块
├── tts.py                  # 语音合成模块
├── ai_client.py            # AI 对话模块
├── audio_player.py         # 音频播放模块
├── test_system.py          # 测试用例
└── docs/                   # 文档
    ├── ARCHITECTURE.md
    ├── MODULES.md
    ├── CONFIG.md
    ├── DEVELOPMENT.md
    └── API.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.sample .env
# 编辑 .env，填入 API Key
```

**必需配置：**
- `ASR_API_KEY` - 语音识别 API 密钥
- `LLM_API_KEY` - AI 对话 API 密钥

### 3. 运行测试

```bash
pytest test_system.py -v
```

### 4. 启动

```bash
python voice_assistant_ai.py
```

或双击 `run_voice.bat`（Windows）

## 使用说明

### 命令

| 按键 | 功能 |
|------|------|
| `Enter` | 开始录音（VAD 自动检测说话） |
| `C` | 清除对话历史 |
| `H` | 显示对话历史 |
| `I` | 切换 Interpreter/AI 模式 |
| `Q` | 退出程序 |

### 工作流程

```
用户语音输入
    ↓
ASR 语音识别 → 文本
    ↓
判断指令类型
    │
    ├── 电脑操作（打开/关闭/创建/删除等）
    │       ↓
    │   Interpreter 模式
    │       ↓
    │   LLM 解析意图 → 生成代码 → 执行 → 语音反馈
    │
    └── 非操作指令
            ↓
        AI 模式
            ↓
        LLM 对话生成 → 语音反馈
```

### 模式说明

**Interpreter 模式** (默认):
- 检测用户指令中的操作关键词
- 自动调用 LLM 生成执行代码
- 支持 Python 和 Bash 命令执行
- 适用于：打开应用、创建文件、截屏、搜索等

**AI 模式**:
- 纯对话模式
- LLM 生成自然语言回复
- 适用于：问答、聊天、咨询等

## 配置说明

### ASR (语音识别)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ASR_API_KEY` | API 密钥 | 必填 |
| `ASR_MODEL` | ASR 模型 | paraformer-realtime-v2 |
| `ASR_BASE_URL` | API 地址 | https://dashscope.aliyuncs.com/api/v1 |

### LLM (AI 对话)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | API 密钥 | 必填 |
| `LLM_MODEL` | AI 模型 | kimi-k2.5 |
| `LLM_BASE_URL` | API 地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |

### 音频

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SAMPLE_RATE` | 采样率 | 44100 |
| `EDGE_TTS_VOICE` | TTS 音色 | zh-CN-XiaoxiaoNeural |

### VAD

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VAD_THRESHOLD` | 声音阈值 | 0.02 |
| `VAD_SILENCE_TIMEOUT` | 静默超时 | 1.5 秒 |
| `VAD_MIN_SPEECH` | 最小语音时长 | 0.3 秒 |

### AI

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SYSTEM_PROMPT` | 系统提示词 | 友好的中文语音助手 |

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
- [API参考](docs/API.md) - 接口文档