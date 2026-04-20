# API 参考

本文件记录各模块的公共接口和 Web UI API。

> **注意**: 项目使用 `src/voice_assistant/` 作为源代码包。以下示例假设项目已正确安装或您正在从项目根目录运行。

---

## Web UI API

Web UI 提供 REST API 和 WebSocket 接口。

### REST API

#### GET /api/config

获取当前配置。

**响应:**
```json
{
  "asr": {
    "model": "paraformer-realtime-v2",
    "language_hints": ["zh", "en"]
  },
  "llm": {
    "model": "kimi-k2.5",
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "audio": {
    "sample_rate": 16000,
    "edge_tts_voice": "zh-CN-XiaoxiaoNeural"
  }
}
```

---

#### POST /api/config

更新配置。

**请求体:**
```json
{
  "llm": {
    "model": "qwen-plus",
    "temperature": 0.8
  }
}
```

**响应:**
```json
{
  "success": true,
  "message": "配置已更新"
}
```

---

#### GET /api/models

获取可用模型列表。

**响应:**
```json
{
  "models": [
    {"id": "kimi-k2.5", "name": "kimi-k2.5"},
    {"id": "qwen-plus", "name": "qwen-plus"},
    {"id": "qwen-turbo", "name": "qwen-turbo"}
  ],
  "current_model": "kimi-k2.5"
}
```

---

#### GET /api/history

获取对话历史。

**响应:**
```json
{
  "conversations": [
    {
      "id": 1,
      "session_id": "default",
      "role": "user",
      "content": "讲个笑话",
      "created_at": "2026-04-14 16:30:00"
    },
    {
      "id": 2,
      "session_id": "default",
      "role": "assistant",
      "content": "给你讲个短的哈：为什么企鹅的肚子是白的...",
      "created_at": "2026-04-14 16:30:05"
    }
  ]
}
```

---

#### POST /api/history/clear

清除对话历史。

**响应:**
```json
{
  "success": true,
  "message": "对话历史已清除"
}
```

---

### WebSocket API

#### /ws/{client_id}

实时聊天 WebSocket 连接。

**连接:**
```javascript
const clientId = 'client_' + Math.random().toString(36).substr(2, 9);
const ws = new WebSocket(`ws://127.0.0.1:8000/ws/${clientId}`);
```

**客户端 → 服务器消息:**

1. **开始对话:**
```json
{
  "type": "start_conversation",
  "title": "新对话"
}
```

2. **加载对话:**
```json
{
  "type": "load_conversation",
  "conversation_id": "uuid-string"
}
```

3. **文本消息:**
```json
{
  "type": "text_message",
  "content": "讲个笑话"
}
```

4. **音频数据:**
```json
{
  "type": "audio_data",
  "data": "base64_encoded_audio_data...",
  "format": "audio/webm"
}
```

5. **TTS 重播:**
```json
{
  "type": "replay_tts",
  "content": "要重播的文本"
}
```

6. **设置更新:**
```json
{
  "type": "update_settings",
  "settings": {
    "model": "qwen-plus",
    "temperature": 0.8,
    "max_tokens": 2000,
    "tts_voice": "zh-CN-YunxiNeural"
  }
}
```

**服务器 → 客户端消息:**

1. **对话开始:**
```json
{
  "type": "conversation_started",
  "conversation_id": "uuid-string"
}
```

2. **语音识别中:**
```json
{
  "type": "asr_processing"
}
```

3. **语音识别结果:**
```json
{
  "type": "asr_result",
  "content": "识别到的文本"
}
```

4. **用户消息:**
```json
{
  "type": "user_message",
  "content": "用户输入的文本"
}
```

5. **AI 思考中:**
```json
{
  "type": "llm_thinking",
  "message": "AI 正在思考..."
}
```

6. **执行中（计算机控制）:**
```json
{
  "type": "executing",
  "message": "正在执行操作..."
}
```

7. **执行完成:**
```json
{
  "type": "execution_complete",
  "message": "操作执行完成"
}
```

8. **流式文本响应:**
```json
{
  "type": "llm_stream",
  "content": "流式输出的文本片段"
}
```

9. **响应完成:**
```json
{
  "type": "llm_complete",
  "content": "完整的响应文本"
}
```

10. **TTS 生成中:**
```json
{
  "type": "tts_generating"
}
```

11. **TTS 音频:**
```json
{
  "type": "tts_audio",
  "data": "base64_encoded_mp3_audio..."
}
```

12. **错误消息:**
```json
{
  "type": "error",
  "message": "错误描述"
}
```

---

## Python 模块 API

## voice_assistant.audio.cloud_asr 模块

### CloudASR 类

```python
from voice_assistant.audio.cloud_asr import CloudASR

asr = CloudASR(api_key=None, model=None)
```

#### 构造函数

```python
def __init__(self, api_key=None, model=None)
```

**参数:**
- `api_key` (str, optional): ASR 服务 API 密钥，默认从环境变量读取
- `model` (str, optional): ASR 模型名称，默认从 `config.asr.model` 读取

---

#### recognize_from_file

```python
def recognize_from_file(self, audio_file_path, sample_rate=None) -> str
```

从音频文件识别语音。

**参数:**
- `audio_file_path` (str): WAV 音频文件路径
- `sample_rate` (int, optional): 采样率，默认从配置读取

**返回:**
- (str): 识别的文本，识别失败返回错误信息

**示例:**
```python
asr = CloudASR()
result = asr.recognize_from_file("test.wav")
print(result)  # "你好"
```

---

#### recognize_from_bytes

```python
def recognize_from_bytes(self, audio_bytes, sample_rate=None) -> str
```

从音频字节数据识别语音。

**参数:**
- `audio_bytes` (bytes): 音频数据（WAV格式或原始PCM）
- `sample_rate` (int, optional): 采样率，默认从配置读取

**返回:**
- (str): 识别的文本，识别失败返回错误信息

**示例:**
```python
with open("test.wav", "rb") as f:
    audio_bytes = f.read()

asr = CloudASR()
result = asr.recognize_from_bytes(audio_bytes)
print(result)  # "你好"
```

---



```python

```

#### 构造函数

```python
def __init__(self, model_path: str, system_prompt: Optional[str] = None)
```

**参数:**
- `system_prompt` (str, optional): 系统提示词

---

#### ask_stream

```python
def ask_stream(self, text: str, conversation_history=None) -> Generator[str, None, None]
```

流式获取回复。

**参数:**
- `text` (str): 用户输入文本
- `conversation_history` (list, optional): 对话历史（本地模式忽略）

**返回:**
- (generator): 流式响应生成器

**示例:**
```python
    for chunk in client.ask_stream("你好"):
        print(chunk, end='')
```

---

#### close

```python
def close(self)
```

关闭客户端，释放资源。

---

## voice_assistant.core.ai_client 模块

### ask_ai_stream

```python
from voice_assistant.core.ai_client import ask_ai_stream

for response in ask_ai_stream("你好", history):
    print(response, end='')
```

使用流式 API 获取 AI 回复（自动选择本地或在线）。

**参数:**
- `text` (str): 用户输入文本
- `conversation_history` (list, optional): 对话历史列表

**返回:**
- (generator): 流式响应生成器

**示例:**
```python
# 简单对话
for response in ask_ai_stream("今天天气怎么样"):
    print(response, flush=True)

# 带历史记录
history = []
for response in ask_ai_stream("我叫小明", history):
    pass

for response in ask_ai_stream("我叫什么名字", history):
    print(response, end='')
```

---


```python

```

获取本地 LLM 客户端单例。

**返回:**

---


```python

```

关闭本地 LLM 客户端。

---

## voice_assistant.audio.vad 模块

### calculate_rms

```python
from voice_assistant.audio.vad import calculate_rms
import numpy as np

rms = calculate_rms(audio_data)
```

计算音频的 RMS 能量值。

**参数:**
- `audio_data` (np.ndarray): 音频数据数组

**返回:**
- (float): RMS 能量值

---

### record_audio

```python
from voice_assistant.audio.vad import record_audio
import numpy as np

audio = record_audio(max_seconds=30)
```

使用 VAD 录制音频，说完自动停止。

**参数:**
- `max_seconds` (int): 最大录音时长，默认 30 秒

**返回:**
- (np.ndarray): 录制的音频数据

**示例:**
```python
# 录音最多 10 秒
audio = record_audio(max_seconds=10)
print(f"录制了 {len(audio)} 个采样点")
```

---

## voice_assistant.audio.tts 模块

### synthesize

```python
from voice_assistant.audio.tts import synthesize

audio_data = synthesize("你好")
```

将文本转换为语音。

**参数:**
- `text` (str): 要转换的文本

**返回:**
- (bytes): MP3 格式的音频数据

**示例:**
```python
from voice_assistant.audio.tts import synthesize
from voice_assistant.audio.player import play_audio

# 合成并播放
audio = synthesize("你好，我是语音助手")
play_audio(audio)
```

---

### preprocess_text

```python
from voice_assistant.audio.tts import preprocess_text

text = preprocess_text("你好世界")
```

文本预处理，使 TTS 发音更自然。

**参数:**
- `text` (str): 原始文本

**返回:**
- (str): 处理后的文本

**处理规则:**
- 句号、感叹号、问号后添加空格
- 逗号、分号、冒号后添加空格
- 多余空格合并

---

## voice_assistant.audio.player 模块

### play_audio

```python
from voice_assistant.audio.player import play_audio

play_audio(audio_data)
```

播放音频数据。

**参数:**
- `audio_data` (bytes): MP3 格式的音频数据

**示例:**
```python
from voice_assistant.audio.tts import synthesize
from voice_assistant.audio.player import play_audio

# 合成并播放
audio = synthesize("你好")
play_audio(audio)
print("播放完成")
```

---

## voice_assistant.security.validation 模块

### RateLimiter 类

```python
from voice_assistant.security.validation import RateLimiter

limiter = RateLimiter(max_requests=10, window_seconds=60)
limiter.check()  # 超限抛出 RateLimitError
```

速率限制器。

**参数:**
- `max_requests` (int): 时间窗口内最大请求数
- `window_seconds` (int): 时间窗口（秒）

---

### validate_text_input

```python
from voice_assistant.security.validation import validate_text_input

cleaned = validate_text_input(user_input)
```

验证文本输入。

**参数:**
- `text` (str): 输入文本

**返回:**
- (str): 验证后的文本

**异常:**
- `InputValidationError`: 输入验证失败

---

### validate_audio_input

```python
from voice_assistant.security.validation import validate_audio_input

cleaned = validate_audio_input(audio_bytes)
```

验证音频输入。

**参数:**
- `audio_bytes` (bytes): 音频数据

**返回:**
- (bytes): 验证后的音频数据

**异常:**
- `InputValidationError`: 输入验证失败

---

## voice_assistant.core.asr_corrector 模块

### correct_asr_result

```python
from voice_assistant.core.asr_corrector import correct_asr_result

corrected = correct_asr_result("打开 open interpreter", history)
```

纠正 ASR 识别结果。

**参数:**
- `text` (str): ASR 原始结果
- `conversation_history` (list, optional): 对话历史

**返回:**
- (str): 纠正后的文本

**示例:**
```python
# 纠正音译错误
result = correct_asr_result("打开 open interpreter")
# 可能返回 "打开 Open Interpreter"
```

---

## voice_assistant.main 模块 (主程序)

### toggle_llm_mode

```python
from voice_assistant.main import toggle_llm_mode

success, mode_name = toggle_llm_mode()
```

切换本地/在线 LLM 模式。

**返回:**
- (tuple[bool, str]): (是否成功, 模式名称)

---

### get_llm_mode

```python
from voice_assistant.main import get_llm_mode

mode = get_llm_mode()  # "本地" 或 "在线"
```

获取当前 LLM 模式。

**返回:**
- (str): "本地" 或 "在线"

---

## voice_assistant.config 模块 (配置)

### config 对象

```python
from voice_assistant.config import config
```

通过 `config` 对象访问配置：

```python
config.asr.model              # ASR 模型
config.asr.base_url           # ASR 服务地址
config.asr.language_hints     # 语言提示
config.llm.model              # AI 模型（在线）
config.llm.local.model_path   # 本地模型路径
config.llm.max_tokens         # 最大响应长度
config.audio.sample_rate      # 采样率
config.audio.edge_tts_voice   # TTS 音色
config.vad.threshold          # 声音检测阈值
config.interpreter.auto_run   # 自动执行代码
```

---

## 配置参考

项目使用配置分离架构：

| 文件 | 内容 |
|------|------|
| `.env` | API Key（敏感信息） |
| `config.yaml` | 模型、参数等（非敏感配置） |

### .env 配置

| 变量 | 说明 |
|------|------|
| `ASR_API_KEY` | ASR 服务 API 密钥 |
| `LLM_API_KEY` | LLM 服务 API 密钥 |

详见 [CONFIG.md](CONFIG.md)。