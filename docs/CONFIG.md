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
| `LLM_API_KEY` | ✅ | AI 对话 API 密钥（在线模式） |

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
  language_hints: ["zh", "en"]
  disfluency_removal_enabled: true
  max_sentence_silence: 1200
  hotwords:
    enabled: true
    config_file: "config/hotwords.json"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `model` | ASR 模型 | paraformer-realtime-v2 |
| `base_url` | ASR 服务地址 | https://dashscope.aliyuncs.com/api/v1 |
| `language_hints` | 语言提示 | ["zh", "en"] |
| `disfluency_removal_enabled` | 过滤语气词 | true |
| `max_sentence_silence` | 句间停顿容忍(ms) | 1200 |
| `hotwords.enabled` | 启用热词 | true |
| `hotwords.config_file` | 热词配置文件 | config/hotwords.json |

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
  use_local: false
  local:
    model_path: "model_weights/gemma-4-E2B-it.litertlm"
    model_name: "gemma-4-E2B-it"
    system_prompt: "你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `model` | AI 模型（在线） | kimi-k2.5 |
| `base_url` | LLM 服务地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| `max_tokens` | 最大响应长度 | 2000 |
| `temperature` | 创造性程度 | 0.7 |
| `use_local` | 使用本地模型 | false |
| `local.model_path` | 本地模型路径 | model_weights/gemma-4-E2B-it.litertlm |
| `local.model_name` | 本地模型名称 | gemma-4-E2B-it |
| `local.system_prompt` | 系统提示词 | 友好的中文语音助手 |
| `local.use_multimodal_audio` | 多模态音频 | false |

**推荐模型（在线）：**

| 模型ID | 说明 |
|--------|------|
| `kimi-k2.5` | Kimi K2.5（推荐） |
| `qwen-turbo` | Qwen Turbo |
| `qwen-plus` | Qwen Plus |

**本地模型：**

| 模型 | 说明 | 大小 |
|------|------|------|
| `gemma-4-E2B-it` | Gemma 4 2B 参数 | ~2.4GB |

### 音频配置

```yaml
audio:
  sample_rate: 16000
  edge_tts_voice: "zh-CN-XiaoxiaoNeural"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `sample_rate` | 采样率 (Hz) | 16000 |
| `edge_tts_voice` | TTS 音色 | zh-CN-XiaoxiaoNeural |

**采样率说明：**
- `16000`: ASR 标准采样率（推荐）
- `44100`: CD 音质
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
  min_speech: 0.15  # 降低阈值，允许短语音（如"北京"）
  wait_timeout: 10
  max_recording: 30
```

| 参数 | 说明 | 默认值 | 单位 |
|------|------|--------|------|
| `threshold` | 声音检测阈值 | 0.02 | RMS 能量 |
| `silence_timeout` | 静默超时 | 1.5 | 秒 |
| `min_speech` | 最小语音时长 | 0.15 | 秒 |
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

### 意图识别配置

```yaml
intent:
  model: "qwen-turbo"  # 轻量模型，适合分类任务
  timeout: 5           # 超时时间（秒）
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `model` | 意图识别使用的 LLM 模型 | qwen-turbo |
| `timeout` | LLM 调用超时时间（秒） | 5 |

**意图分类机制**：

采用 **LLM 优先 + 关键词兜底** 策略：

1. **优先调用云端 LLM**（qwen-turbo）进行语义理解，返回 JSON 格式的意图类型和置信度
2. **LLM 失败或置信度 < 0.3** 时，自动降级到关键词匹配
3. 三种意图类型：
   - `computer_control`：电脑操作指令
   - `query_answer`：事实性问题查询
   - `ordinary_chat`：普通闲聊对话

详见 [MODULES.md](MODULES.md) 中的路由服务说明。

---

## 本地模型配置

### 下载模型

```bash
# 使用 huggingface-cli
huggingface-cli download litert-community/gemma-4-E2B-it-litert-lm \
  --local-dir ./model_weights
```

或从 HuggingFace 手动下载：
https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm

### 模型文件

下载后将模型文件放置到：
```
model_weights/gemma-4-E2B-it.litertlm
```

### 切换模式

**方式 1：运行时切换**
- 按 `L` 键切换本地/在线模式

**方式 2：配置文件**
```yaml
llm:
  use_local: true  # 强制使用本地模型
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
  language_hints: ["zh", "en"]
  disfluency_removal_enabled: true
  max_sentence_silence: 1200
  hotwords:
    enabled: true
    config_file: "config/hotwords.json"

llm:
  model: "kimi-k2.5"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  max_tokens: 2000
  temperature: 0.7
  use_local: false
  local:
    model_path: "model_weights/gemma-4-E2B-it.litertlm"
    model_name: "gemma-4-E2B-it"
    system_prompt: "你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。"
    use_multimodal_audio: false  # 直接将音频送给本地模型，跳过 ASR

audio:
  sample_rate: 16000
  edge_tts_voice: "zh-CN-XiaoxiaoNeural"

vad:
  threshold: 0.02
  silence_timeout: 1.5
  min_speech: 0.15
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

intent:
  model: "qwen-turbo"
  timeout: 5
```

---

## 环境验证

运行测试验证配置是否正确：

```bash
source .venv/bin/activate
pytest test_system.py -v
```

测试会检查：
- 所有依赖包是否正确安装
- 配置文件是否正确加载
- API 密钥是否有效
- 音频设备是否可用
- 本地模型是否可用（如已下载）