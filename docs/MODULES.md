# 模块说明

## 项目结构

```
voice-assistant/
├── config.yaml           # 配置文件
├── .env                  # 环境变量（API密钥）
├── run.py                # 入口脚本
├── start.sh              # 启动脚本
├── pyproject.toml        # 项目配置
└── src/voice_assistant/  # 源代码包
    ├── __init__.py
    ├── main.py           # 主程序
    ├── config/           # 配置模块
    ├── audio/            # 音频模块
    ├── core/             # 核心模块
    ├── executors/        # 执行器模块
    ├── models/           # 数据模型
    ├── services/         # 服务模块
    └── security/         # 安全模块
```

## 模块概览

| 模块路径 | 功能 | 依赖服务 |
|----------|------|----------|
| `voice_assistant.main` | 主程序，流程控制，模式切换 | 全部模块 |
| `voice_assistant.audio.cloud_asr` | 阿里云语音识别 | DashScope API |
| `voice_assistant.core.local_llm` | 本地 LLM 推理 | LiteRT-LM |
| `voice_assistant.audio.vad` | 语音活动检测 | sounddevice |
| `voice_assistant.audio.tts` | 语音合成 | Edge-TTS |
| `voice_assistant.core.ai_client` | AI对话客户端（在线/本地） | LLM API / LiteRT-LM |
| `voice_assistant.audio.player` | 音频播放 | pygame |
| `voice_assistant.security.validation` | 安全工具（输入验证、限流） | - |
| `voice_assistant.core.asr_corrector` | ASR 结果纠错 | LLM |
| `voice_assistant.executors.interpreter` | Open Interpreter 执行器 | Open Interpreter |
| `voice_assistant.executors.computer` | 计算机控制执行器 | pyautogui |
| `voice_assistant.executors.chat` | 对话执行器 | LLM |
| `voice_assistant.services.router` | 指令路由服务 | - |

---

## voice_assistant.main (主程序)

### 功能
- 串联各模块，协调工作流程
- 处理用户交互（键盘输入）
- 管理对话历史
- 支持 Interpreter 和 AI 两种模式切换
- 支持本地/在线 LLM 切换

### 核心函数

```python
def toggle_llm_mode() -> tuple[bool, str]
    """切换本地/在线 LLM 模式"""

def get_llm_mode() -> str
    """获取当前 LLM 模式"""

def recognize(audio_bytes) -> str
    """语音识别"""

def speak_and_play(text: str)
    """语音合成并播放"""

def main()
    """主循环"""
```

### 工作模式

#### Interpreter 模式 (默认)
- 检测用户指令中的操作关键词
- 调用 LLM 生成可执行代码
- 执行 Python 或 Bash 代码
- 返回执行结果

**操作关键词**:
```python
computer_keywords = [
    "打开", "关闭", "创建", "删除", "截屏", "截图", "新建", "运行", "执行",
    "打开文件", "关闭窗口", "启动", "停止", "复制", "移动", "重命名",
    "搜索", "查找", "下载", "上传", "安装", "卸载", "控制", "操作"
]
```

#### AI 模式
- 纯对话模式
- 使用流式 API 获取 LLM 回复
- 保持对话上下文

### 交互控制

| 按键 | 功能 |
|------|------|
| Enter | 开始录音 |
| C | 清除对话历史 |
| H | 显示对话历史 |
| I | 切换 Interpreter/AI 模式 |
| L | 切换 本地/在线 LLM |
| Q | 退出程序 |

### 配置

项目使用配置分离架构：
- `.env` - 敏感信息（API Key）
- `config.yaml` - 非敏感配置

详见 [CONFIG.md](CONFIG.md)。

---

## voice_assistant.audio.cloud_asr (语音识别)

### 功能
- 使用阿里云 DashScope Paraformer 进行语音识别
- 支持文件和字节输入
- 支持热词优化
- 中英文混合识别优化

### 类: CloudASR

```python
class CloudASR:
    def __init__(self, api_key=None, model=None)
        """初始化云端ASR"""

    def recognize_from_file(self, audio_file_path, sample_rate=None)
        """从音频文件识别"""

    def recognize_from_bytes(self, audio_bytes, sample_rate=None)
        """从音频字节识别"""
```

### 热词管理

```python
class HotwordsManager:
    def create_vocabulary(self, vocabulary: list) -> str
        """创建热词列表"""

    def load_hotwords_from_file(self, config_file: str) -> list
        """从文件加载热词配置"""
```

### 配置变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ASR_API_KEY` | ASR服务API密钥 | 必填 |
| `ASR_MODEL` | ASR模型 | paraformer-realtime-v2 |
| `ASR_BASE_URL` | ASR服务地址 | https://dashscope.aliyuncs.com/api/v1 |

---

## voice_assistant.core.local_llm (本地 LLM)

### 功能
- 使用 LiteRT-LM 进行本地推理
- 支持流式输出
- 与在线 LLM 兼容的接口

### 类: LocalLLMEngine

```python
class LocalLLMEngine:
    def __init__(self, model_path: str, system_prompt: str = None)
        """初始化本地 LLM 引擎"""

    def send_message(self, text: str) -> str
        """发送消息并获取完整回复"""

    def send_message_stream(self, text: str) -> Generator[str, None, None]
        """发送消息并流式获取回复"""

    def close(self)
        """关闭引擎，释放资源"""
```

### 类: LocalLLMClient

```python
class LocalLLMClient:
    def __init__(self, model_path: str, system_prompt: str = None)
        """初始化客户端"""

    def ask_stream(self, text: str, conversation_history=None) -> Generator
        """流式获取回复（兼容在线 LLM 接口）"""

    def close(self)
        """关闭客户端"""
```

### 配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `llm.local.model_path` | 模型文件路径 | model_weights/gemma-4-E2B-it.litertlm |
| `llm.local.model_name` | 模型名称 | gemma-4-E2B-it |
| `llm.local.system_prompt` | 系统提示词 | 友好的中文语音助手 |

---

## voice_assistant.audio.vad (语音活动检测)

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

## voice_assistant.audio.tts (语音合成)

### 功能
- 使用 Microsoft Edge-TTS 进行语音合成
- 支持中文自然语音

### 主要函数

```python
def preprocess_text(text)
    """文本预处理，使TTS发音更自然"""

def synthesize(text, output_path=None)
    """语音合成，返回音频字节数据"""
```

### 配置变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `EDGE_TTS_VOICE` | TTS音色 | zh-CN-XiaoxiaoNeural |

---

## voice_assistant.core.ai_client (AI对话)

### 功能
- 使用 LLM API 进行 AI 对话
- 支持本地/在线模型切换
- 支持流式输出
- 管理对话上下文

### 主要函数

```python
def get_local_llm_client() -> LocalLLMClient
    """获取本地 LLM 客户端（单例）"""

def close_local_llm_client()
    """关闭本地 LLM 客户端"""

def ask_ai_stream(text, conversation_history=None)
    """流式获取AI回复（自动选择本地或在线）"""

def ask_local_ai_stream(text, conversation_history=None)
    """使用本地模型获取AI回复"""

def ask_online_ai_stream(text, conversation_history=None)
    """使用在线API获取AI回复"""
```

### 配置变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM服务API密钥 | 必填 |
| `LLM_MODEL` | AI模型 | kimi-k2.5 |
| `LLM_BASE_URL` | LLM服务地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |

---

## voice_assistant.audio.player (音频播放)

### 功能
- 使用 pygame 播放音频
- 自动清理临时文件

### 主要函数

```python
def play_audio(audio_data)
    """播放音频数据（MP3格式）"""
```

---

## voice_assistant.security.validation (安全工具)

### 功能
- 输入验证
- 速率限制
- 安全常量

### 主要类和函数

```python
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int)
    def check(self) -> None  # 超限抛出 RateLimitError

def validate_text_input(text: str) -> str
    """验证文本输入"""

def validate_audio_input(audio_bytes: bytes) -> bytes
    """验证音频输入"""
```

### 安全常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `MAX_TEXT_LENGTH` | 1000 | 最大文本长度 |
| `MAX_AUDIO_SIZE` | 10MB | 最大音频大小 |

---

## voice_assistant.core.asr_corrector (ASR 纠错)

### 功能
- LLM 驱动的 ASR 结果纠错
- 检测音译错误并修正
- 基于对话上下文优化

### 主要函数

```python
def correct_asr_result(text: str, conversation_history: list = None) -> str
    """纠正 ASR 识别结果"""

def _needs_correction(text: str) -> bool
    """判断是否需要纠错"""
```

---

## voice_assistant.executors (执行器模块)

### BaseExecutor (基类)

```python
class BaseExecutor(ABC):
    @abstractmethod
    def execute(self, text: str, conversation_history: list = None) -> str
        """执行指令"""
```

### ChatExecutor (对话执行器)

```python
class ChatExecutor(BaseExecutor):
    def execute(self, text: str, conversation_history: list = None) -> str
        """纯对话模式"""
```

### ComputerExecutor (计算机控制执行器)

```python
class ComputerExecutor(BaseExecutor):
    def execute(self, text: str, conversation_history: list = None) -> str
        """计算机控制操作"""
```

### InterpreterExecutor (Open Interpreter 执行器)

```python
class InterpreterExecutor(BaseExecutor):
    def execute(self, text: str, conversation_history: list = None) -> str
        """使用 Open Interpreter 执行复杂任务"""
```

---

## voice_assistant.services.router (路由服务)

### 功能
- 分析用户指令意图
- 路由到合适的执行器

### 类: CommandRouter

```python
class CommandRouter:
    def route(self, text: str, conversation_history: list = None) -> str
        """路由指令到合适的执行器"""
```

---

## 测试

### 测试覆盖

| 测试类 | 测试内容 |
|--------|----------|
| `TestImports` | 验证所有依赖包可导入 |
| `TestConfiguration` | 验证配置正确加载 |
| `TestLLMAPI` | 验证 LLM API 连接 |
| `TestCloudASR` | 验证云端ASR功能 |
| `TestEdgeTTS` | 验证TTS合成功能 |
| `TestAudioDevices` | 验证音频设备可用性 |
| `TestVoiceAssistantAI` | 验证主模块加载 |
| `TestASRCorrector` | 验证 ASR 纠错功能 |
| `TestSecurityUtils` | 验证安全工具功能 |

### 运行测试

```bash
# 使用 pytest
pytest tests/ -v

# 或使用 uv
uv run pytest tests/ -v
```