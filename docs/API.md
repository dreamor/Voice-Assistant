# API 参考

本文件记录各模块的公共接口。

---

## cloud_asr 模块

### CloudASR 类

```python
from cloud_asr import CloudASR

asr = CloudASR(api_key=None, model=None)
```

#### 构造函数

```python
def __init__(self, api_key=None, model=None)
```

**参数:**
- `api_key` (str, optional): ASR 服务 API 密钥，默认从 `config.asr.api_key` 读取
- `model` (str, optional): ASR 模型名称，默认从 `config.asr.model` 读取

---

#### recognize_from_file

```python
def recognize_from_file(self, audio_file_path, sample_rate=44100) -> str
```

从音频文件识别语音。

**参数:**
- `audio_file_path` (str): WAV 音频文件路径
- `sample_rate` (int): 采样率，默认 44100

**返回:**
- (str): 识别的文本，识别失败返回错误信息

**示例:**
```python
asr = CloudASR()
result = asr.recognize_from_file("test.wav", 44100)
print(result)  # "你好"
```

---

#### recognize_from_bytes

```python
def recognize_from_bytes(self, audio_bytes, sample_rate=44100) -> str
```

从音频字节数据识别语音。

**参数:**
- `audio_bytes` (bytes): 音频数据（WAV格式或原始PCM）
- `sample_rate` (int): 采样率，默认 44100

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

## vad 模块

### calculate_rms

```python
from vad import calculate_rms
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
from vad import record_audio
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

## tts 模块

### synthesize

```python
from tts import synthesize

audio_data = synthesize("你好")
```

将文本转换为语音。

**参数:**
- `text` (str): 要转换的文本

**返回:**
- (bytes): MP3 格式的音频数据

**示例:**
```python
from tts import synthesize
from audio_player import play_audio

# 合成并播放
audio = synthesize("你好，我是语音助手")
play_audio(audio)
```

---

### preprocess_text

```python
from tts import preprocess_text

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

## ai_client 模块

### ask_ai_stream

```python
from ai_client import ask_ai_stream

for response in ask_ai_stream("你好", history):
    print(response, end='')
```

使用流式 API 获取 AI 回复。

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

## audio_player 模块

### play_audio

```python
from audio_player import play_audio

play_audio(audio_data)
```

播放音频数据。

**参数:**
- `audio_data` (bytes): MP3 格式的音频数据

**示例:**
```python
from tts import synthesize
from audio_player import play_audio

# 合成并播放
audio = synthesize("你好")
play_audio(audio)
print("播放完成")
```

---

## voice_assistant_ai 模块 (主程序)

### call_llm

```python
from voice_assistant_ai import call_llm

response = call_llm("你好", system_prompt="你是一个助手")
```

直接调用 LLM API。

**参数:**
- `prompt` (str): 用户提示
- `system_prompt` (str, optional): 系统提示

**返回:**
- (str): LLM 响应

---

### execute_code

```python
from voice_assistant_ai import execute_code

result = execute_code("print('hello')", "python")
```

执行代码。

**参数:**
- `code` (str): 要执行的代码
- `language` (str): 语言类型，"python" 或 "bash"

**返回:**
- (str): 执行结果或错误信息

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

### config.yaml 配置

通过 `from config import config` 访问配置对象：

```python
config.asr.model          # ASR 模型
config.asr.base_url       # ASR 服务地址
config.llm.model          # AI 模型
config.llm.max_tokens     # 最大响应长度
config.audio.sample_rate  # 采样率
config.audio.edge_tts_voice  # TTS 音色
config.vad.threshold      # 声音检测阈值
config.interpreter.auto_run  # 自动执行代码
```

详见 [CONFIG.md](CONFIG.md)。