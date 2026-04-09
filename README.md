# Voice Assistant

中文语音助手 - 麦克风收音 → 语音识别 → AI对话 → 语音合成 → 扬声器播放

## 功能特性

- **语音识别 (STT)**: 阿里云 DashScope Paraformer 实时识别
- **AI 对话**: OpenRouter API，支持多模型
- **语音合成 (TTS)**: Microsoft Edge-TTS，自然流畅
- **VAD 语音检测**: 自动检测说话开始/结束，无需手动操作
- **对话上下文**: 支持多轮对话，保持上下文

## 项目结构

```
voice_assistant/
├── .env                     # 配置文件
├── requirements.txt          # 依赖清单
├── voice_assistant_ai.py    # 主程序
├── cloud_asr.py            # 语音识别模块
├── vad.py                  # 语音检测模块
├── tts.py                  # 语音合成模块
├── ai_client.py            # AI 对话模块
├── audio_player.py         # 音频播放模块
├── test_system.py          # 测试用例
└── run_voice.bat          # Windows 启动脚本
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

或直接双击 `run_voice.bat`

## 使用说明

### 命令

| 按键 | 功能 |
|------|------|
| `Enter` | 开始录音（VAD 自动检测说话） |
| `C` | 清除对话历史 |
| `H` | 显示对话历史 |
| `Q` | 退出程序 |

### 工作流程

1. 按 `Enter` 开始录音
2. 对着麦克风说话
3. 说完后静默约 1.5 秒自动停止录音
4. 程序自动进行语音识别
5. AI 生成回复
6. 语音合成并播放
7. 重复对话或按 `Q` 退出

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

### VAD 参数

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VAD_THRESHOLD` | 声音阈值 | 0.02 |
| `VAD_SILENCE_TIMEOUT` | 静默超时（秒） | 1.5 |
| `VAD_MIN_SPEECH` | 最小语音时长（秒） | 0.3 |
| `VAD_WAIT_TIMEOUT` | 等待超时（秒） | 10 |

### AI 参数

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AI_MAX_RETRIES` | 最大重试次数 | 3 |
| `AI_RETRY_DELAY` | 重试延迟（秒） | 2 |
| `SYSTEM_PROMPT` | 系统提示词 | 友好的中文语音助手 |

## 模块说明

| 模块 | 功能 |
|------|------|
| `cloud_asr.py` | 阿里云 ASR 语音识别 |
| `vad.py` | VAD 语音活动检测 |
| `tts.py` | Edge-TTS 语音合成 |
| `ai_client.py` | OpenRouter AI 对话 |
| `audio_player.py` | pygame 音频播放 |

## 测试

```bash
pytest test_system.py -v
```

测试覆盖：依赖包、配置读取、API 连接、各模块功能
