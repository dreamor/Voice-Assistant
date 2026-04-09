# 模块说明

## 模块概览

| 模块文件 | 功能 | 依赖服务 |
|----------|------|----------|
| `voice_assistant_ai.py` | 主程序，流程控制 | 全部模块 |
| `cloud_asr.py` | 阿里云语音识别 | DashScope API |
| `vad.py` | 语音活动检测 | sounddevice |
| `tts.py` | 语音合成 | Edge-TTS |
| `ai_client.py` | AI对话客户端 | OpenRouter API |
| `audio_player.py` | 音频播放 | pygame |

---

## voice_assistant_ai.py (主程序)

### 功能
- 串联各模块，协调工作流程
- 处理用户交互（键盘输入）
- 管理对话历史
- 支持 Interpreter 和 AI 两种模式

### 主要函数

```python
def call_llm(prompt: str, system_prompt: str = None) -> str
    """直接调用 LLM API"""

def execute_code(code: str, language: str = "python") -> str
    """执行代码（Python/Bash）"""

def handle_with_interpreter(user_text: str) -> str
    """使用 Interpreter 模式处理"""

def handle_with_ai(user_text: str) -> str
    """使用 AI 聊天模式处理"""

def recognize(audio_bytes)
    """语音识别"""

def speak_and_play(text: str)
    """语音合成并播放"""

def main()
    """主循环"""
```

### 工作模式

1. **Interpreter 模式**: 分析用户意图，必要时执行代码
2. **AI 聊天模式**: 纯粹的 AI 对话

### 交互控制

| 按键 | 功能 |
|------|------|
| Enter | 开始录音 |
| C | 清除对话历史 |
| H | 显示对话历史 |
| I | 切换 Interpreter/AI 模式 |
| Q | 退出程序 |

---

## cloud_asr.py (语音识别)

### 功能
- 使用阿里云 DashScope Paraformer 进行语音识别
- 支持文件和字节输入

### 类: CloudASR

```python
class CloudASR:
    def __init__(self, api_key=None, model=None)
        """初始化云端ASR"""

    def recognize_from_file(self, audio_file_path, sample_rate=44100)
        """从音频文件识别"""

    def recognize_from_bytes(self, audio_bytes, sample_rate=44100)
        """从音频字节识别"""
```

### 使用示例

```python
from cloud_asr import CloudASR

asr = CloudASR(api_key="your-api-key", model="paraformer-realtime-v2")
result = asr.recognize_from_file("audio.wav")
print(result)  # 识别结果文本
```

### 配置变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ASR_API_KEY` | ASR服务API密钥 | 必填 |
| `ASR_MODEL` | ASR模型 | paraformer-realtime-v2 |
| `ASR_BASE_URL` | ASR服务地址 | https://dashscope.aliyuncs.com/api/v1 |

---

## vad.py (语音活动检测)

### 功能
- 实时监听麦克风输入
- 自动检测说话开始（声音能量超过阈值）
- 静默超时后自动停止录音

### 主要函数

```python
def calculate_rms(audio_data)
    """计算音频RMS能量"""

def record_audio(max_seconds=30)
    """使用VAD录制音频，返回numpy数组"""
```

### VAD 参数

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VAD_THRESHOLD` | 声音检测阈值 | 0.02 |
| `VAD_SILENCE_TIMEOUT` | 静默超时(秒) | 1.5 |
| `VAD_MIN_SPEECH` | 最小语音时长(秒) | 0.3 |
| `VAD_WAIT_TIMEOUT` | 等待超时(秒) | 10 |

### 工作原理

```
1. 持续监听麦克风输入
2. 计算每个音频块的 RMS 能量
3. RMS > VAD_THRESHOLD → 开始录音
4. 录音中 RMS < VAD_THRESHOLD → 计时
5. 静默时长 > VAD_SILENCE_TIMEOUT → 停止录音
```

---

## tts.py (语音合成)

### 功能
- 使用 Microsoft Edge-TTS 进行语音合成
- 支持中文自然语音

### 主要函数

```python
def preprocess_text(text)
    """文本预处理，使TTS发音更自然"""

def synthesize(text)
    """语音合成，返回音频字节数据"""
```

### 使用示例

```python
from tts import synthesize

audio_data = synthesize("你好，我是语音助手")
# audio_data 是 MP3 格式的字节数据
```

### 配置变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `EDGE_TTS_VOICE` | TTS音色 | zh-CN-XiaoxiaoNeural |

### 可用音色

| 音色ID | 说明 |
|--------|------|
| zh-CN-XiaoxiaoNeural | 晓晓（女声） |
| zh-CN-YunxiNeural | 云希（男声） |
| zh-CN-YunyangNeural | 云扬（男声） |

---

## ai_client.py (AI对话)

### 功能
- 使用 OpenRouter API 进行 AI 对话
- 支持流式输出
- 管理对话上下文

### 主要函数

```python
def ask_ai_stream(text, conversation_history=None)
    """流式获取AI回复，返回生成器"""
```

### 使用示例

```python
from ai_client import ask_ai_stream

history = []
for response in ask_ai_stream("你好", history):
    print(response, end='')

# response 是生成器，需要迭代获取
```

### 配置变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM服务API密钥 | 必填 |
| `LLM_MODEL` | AI模型 | kimi-k2.5 |
| `LLM_BASE_URL` | LLM服务地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| `SYSTEM_PROMPT` | 系统提示词 | 友好的中文语音助手 |

---

## audio_player.py (音频播放)

### 功能
- 使用 pygame 播放音频
- 自动清理临时文件

### 主要函数

```python
def play_audio(audio_data)
    """播放音频数据（MP3格式）"""
```

### 使用示例

```python
from audio_player import play_audio
from tts import synthesize

audio = synthesize("你好")
play_audio(audio)
```

### 技术细节

- 使用临时文件存储 MP3 数据
- 播放完成后自动删除临时文件
- 使用 pygame.mixer 进行播放控制

---

## test_system.py (测试)

### 测试覆盖

| 测试类 | 测试内容 |
|--------|----------|
| `TestImports` | 验证所有依赖包可导入 |
| `TestConfiguration` | 验证配置正确加载 |
| `TestOpenRouterAPI` | 验证 OpenRouter API 连接 |
| `TestCloudASR` | 验证云端ASR功能 |
| `TestEdgeTTS` | 验证TTS合成功能 |
| `TestAudioDevices` | 验证音频设备可用性 |
| `TestVoiceAssistantAI` | 验证主模块加载 |

### 运行测试

```bash
pytest test_system.py -v
```