# 配置说明

## 配置架构

项目采用**配置分离**架构：

| 文件 | 内容 | 说明 |
|------|------|------|
| `.env` | API Key 等敏感信息 | 不提交到版本控制 |
| `config.yaml` | 非敏感配置 | 提交到版本控制 |

### 创建配置

```bash
cp .env.example .env
# 编辑 .env 填入 API Key
```

---

## .env 配置（敏感信息）

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `ASR_API_KEY` | ✅ | 语音识别 API 密钥 |
| `LLM_API_KEY` | ✅ | AI 对话 API 密钥 |

### 获取 API Key

访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)：
1. 注册/登录阿里云账号
2. 开通语音识别服务和模型服务
3. 在「API-KEY管理」中创建 API Key

ASR 和 LLM 可使用相同的 API Key。

---

## config.yaml 配置（非敏感信息）

### 应用配置

```yaml
app:
  name: "Voice Assistant"
  version: "2.0.0"
```

### ASR 配置（语音识别）

```yaml
asr:
  model: "paraformer-realtime-v2"
  base_url: "https://dashscope.aliyuncs.com/api/v1"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `model` | ASR 模型 | paraformer-realtime-v2 |
| `base_url` | ASR 服务地址 | https://dashscope.aliyuncs.com/api/v1 |

**可用模型：**

| 模型 | 说明 |
|------|------|
| `paraformer-realtime-v2` | 实时语音识别 v2（推荐） |
| `paraformer-realtime-8k-v2` | 实时识别，8kHz 采样率 |

### LLM 配置（AI 对话）

```yaml
llm:
  model: "kimi-k2.5"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  max_tokens: 2000
  temperature: 0.7
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `model` | AI 模型 | kimi-k2.5 |
| `base_url` | LLM 服务地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| `max_tokens` | 最大响应长度 | 2000 |
| `temperature` | 创造性程度 | 0.7 |

**推荐模型：**

| 模型ID | 说明 |
|--------|------|
| `kimi-k2.5` | Kimi K2.5（推荐） |
| `qwen-turbo` | Qwen Turbo |
| `qwen-plus` | Qwen Plus |

### 音频配置

```yaml
audio:
  sample_rate: 44100
  edge_tts_voice: "zh-CN-XiaoxiaoNeural"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `sample_rate` | 采样率 (Hz) | 44100 |
| `edge_tts_voice` | TTS 音色 | zh-CN-XiaoxiaoNeural |

**采样率说明：**
- `44100`: CD 音质，推荐
- `16000`: 低采样率，文件更小
- `48000`: 高音质

**Edge-TTS 中文音色：**

| 音色ID | 描述 |
|--------|------|
| `zh-CN-XiaoxiaoNeural` | 晓晓（女声）- 推荐 |
| `zh-CN-YunxiNeural` | 云希（男声） |
| `zh-CN-YunyangNeural` | 云扬（男声） |

### VAD 配置（语音检测）

```yaml
vad:
  threshold: 0.02
  silence_timeout: 1.5
  min_speech: 0.3
  wait_timeout: 10
  max_recording: 30
```

| 参数 | 说明 | 默认值 | 单位 |
|------|------|--------|------|
| `threshold` | 声音检测阈值 | 0.02 | RMS 能量 |
| `silence_timeout` | 静默超时 | 1.5 | 秒 |
| `min_speech` | 最小语音时长 | 0.3 | 秒 |
| `wait_timeout` | 等待超时 | 10 | 秒 |
| `max_recording` | 最大录音时长 | 30 | 秒 |

**参数调优：**

- **threshold（灵敏度）**
  - `0.01`: 非常灵敏，可能捕获背景噪音
  - `0.02`: 默认值，正常环境
  - `0.05`: 较不灵敏，需要较大声音

- **silence_timeout（停止延迟）**
  - `1.0`: 快速响应
  - `1.5`: 默认值，自然对话停顿
  - `2.0`: 较长等待，允许思考停顿

### Open Interpreter 配置

```yaml
interpreter:
  auto_run: true
  verbose: false
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `auto_run` | 自动执行代码（无需确认） | true |
| `verbose` | 详细日志输出 | false |

### 对话历史配置

```yaml
history:
  max_turns: 20
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `max_turns` | 最大对话轮数 | 20 |

### 日志配置

```yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(levelname)s - %(message)s"
```

---

## 完整配置示例

### .env

```env
# 敏感配置 - 不要提交到版本控制
ASR_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### config.yaml

```yaml
# Voice Assistant 配置文件

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
  wait_timeout: 10
  max_recording: 30

interpreter:
  auto_run: true
  verbose: false

history:
  max_turns: 20

logging:
  level: "INFO"
  format: "%(asctime)s - %(levelname)s - %(message)s"
```

---

## 环境验证

运行测试验证配置是否正确：

```bash
pytest test_system.py -v
```

测试会检查：
- 所有依赖包是否正确安装
- 配置文件是否正确加载
- API 密钥是否有效
- 音频设备是否可用