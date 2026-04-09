# 开发指南

## 环境准备

### 系统要求

- **Python**: 3.10+（本地模型需要）
- **操作系统**: macOS / Linux / Windows

### 1. 安装 uv

uv 是一个快速的 Python 包管理器，比 pip 快 10-100 倍。

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 安装依赖

```bash
# 克隆或下载项目代码
cd voice-assistant-ai

# 使用启动脚本（推荐）
./start.sh

# 或手动安装
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

uv pip install -e .
```

### 3. 安装本地模型支持（可选）

如需使用本地 LLM：

```bash
uv pip install -e ".[local-llm]"
```

### 4. 配置环境变量

```bash
# 复制配置示例
cp .env.example .env

# 编辑 .env 填入 API 密钥
# 必须填写:
# - ASR_API_KEY (语音识别)
# - LLM_API_KEY (AI 对话，在线模式)
```

### 5. 验证环境

```bash
# 运行测试
uv run pytest test_system.py -v

# 测试单个模块
python -c "from vad import record_audio; print('VAD OK')"
python -c "from tts import synthesize; print('TTS OK')"
python -c "from ai_client import ask_ai_stream; print('AI OK')"
```

---

## 运行

### 启动语音助手

```bash
# 使用启动脚本（推荐）
./start.sh

# 或直接运行
python voice_assistant_ai.py
```

### 交互控制

```
[ENTER=Record / C=Clear / H=History / I=Toggle / L=LLM / Q=Quit] (模式:Interpreter, LLM:在线):
```

| 按键 | 功能 |
|------|------|
| Enter | 开始录音（VAD自动检测说话） |
| C | 清除对话历史 |
| H | 显示对话历史 |
| I | 切换 Interpreter/AI 模式 |
| L | 切换 本地/在线 LLM 模式 |
| Q | 退出程序 |

### LLM 模式切换

按 `L` 键可在本地和在线模式间切换：

| 模式 | 模型 | 特点 |
|------|------|------|
| 在线 | kimi-k2.5 | 需网络，响应快，能力强 |
| 本地 | gemma-4-E2B-it | 离线运行，隐私保护 |

---

## 开发

### 代码结构

```
voice_assistant/
├── voice_assistant_ai.py      # 主程序
├── cloud_asr.py               # 语音识别
├── vad.py                     # 语音检测
├── tts.py                     # 语音合成
├── ai_client.py               # AI对话（在线/本地）
├── local_llm.py               # 本地 LLM 推理
├── audio_player.py            # 音频播放
├── security_utils.py          # 安全工具
├── asr_corrector.py           # ASR 纠错
├── interpreter_executor.py    # Open Interpreter 执行器
├── test_system.py             # 测试用例
├── test_executors.py          # 执行器测试
├── pyproject.toml             # 项目配置（uv）
├── config.yaml                # 应用配置
├── .env                       # 环境变量（需创建）
├── model_weights/             # 本地模型目录
│   └── gemma-4-E2B-it.litertlm
└── docs/                      # 文档
```

### 模块开发

#### 添加新的 ASR 引擎

```python
# 1. 创建新模块 asr_new.py
class NewASR:
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def recognize_from_bytes(self, audio_bytes, sample_rate=16000):
        # 实现识别逻辑
        result = do_recognize(audio_bytes)
        return result

# 2. 修改 voice_assistant_ai.py 导入
from asr_new import NewASR

# 3. 创建 ASR 实例
asr = NewASR(api_key=..., model=...)
```

#### 添加新的 TTS 引擎

```python
# 1. 创建新模块 tts_new.py
def synthesize(text):
    # 调用新的 TTS 服务
    audio = call_tts_service(text)
    return audio

# 2. 修改 voice_assistant_ai.py 导入
from tts_new import synthesize
```

#### 添加新的执行器

```python
# 1. 创建新执行器 executors/new_executor.py
from executors.base_executor import BaseExecutor

class NewExecutor(BaseExecutor):
    def can_handle(self, intent_type: str) -> bool:
        return intent_type == "NEW_TYPE"

    def execute(self, **kwargs) -> dict:
        # 实现执行逻辑
        return {"response": "执行结果"}

# 2. 在 voice_assistant_ai.py 中注册
from executors.new_executor import NewExecutor
executors.append(NewExecutor())
```

### 调试

#### 本地测试 VAD

```python
from vad import record_audio, calculate_rms
import numpy as np

# 测试 RMS 计算
test_audio = np.random.randn(16000) * 0.1
rms = calculate_rms(test_audio)
print(f"RMS: {rms}")

# 测试录音
audio = record_audio(max_seconds=5)
print(f"Recorded: {len(audio)} samples")
```

#### 本地测试 TTS

```python
from tts import synthesize

audio = synthesize("你好，这是一个测试")
print(f"Audio size: {len(audio)} bytes")
```

#### 本地测试 AI

```python
from ai_client import ask_ai_stream

# 在线模式
for response in ask_ai_stream("你好"):
    print(response, end='')

# 本地模式
from ai_client import get_local_llm_client

client = get_local_llm_client()
if client:
    for chunk in client.ask_stream("你好"):
        print(chunk, end='')
```

---

## 测试

### 运行全部测试

```bash
uv run pytest test_system.py -v
```

### 运行特定测试

```bash
# 只测试配置
uv run pytest test_system.py::TestConfiguration -v

# 只测试 ASR
uv run pytest test_system.py::TestCloudASR -v

# 只测试执行器
uv run pytest test_executors.py -v
```

### 测试覆盖

- `TestImports`: 依赖包导入
- `TestConfiguration`: 配置加载
- `TestLLMAPI`: LLM API 连接
- `TestCloudASR`: 语音识别
- `TestEdgeTTS`: 语音合成
- `TestAudioDevices`: 音频设备
- `TestVoiceAssistantAI`: 主模块
- `TestASRCorrector`: ASR 纠错
- `TestSecurityUtils`: 安全工具

---

## 本地模型开发

### 下载模型

```bash
# 使用 huggingface-cli
huggingface-cli download litert-community/gemma-4-E2B-it-litert-lm \
  --local-dir ./model_weights

# 或手动下载
# https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm
```

### 模型文件位置

```
model_weights/
└── gemma-4-E2B-it.litertlm  # ~2.4GB
```

### 配置本地模型

编辑 `config.yaml`:

```yaml
llm:
  use_local: false  # 设为 true 强制使用本地模式
  local:
    model_path: "model_weights/gemma-4-E2B-it.litertlm"
    model_name: "gemma-4-E2B-it"
    system_prompt: "你是一个友好的中文语音助手..."
```

### 测试本地模型

```python
from local_llm import LocalLLMClient

with LocalLLMClient("model_weights/gemma-4-E2B-it.litertlm") as client:
    for chunk in client.ask_stream("你好"):
        print(chunk, end='')
```

---

## 常见问题

### Q: 测试通过但程序无法运行

1. 检查 `.env` 文件是否存在
2. 检查 API 密钥是否有效
3. 检查网络连接

### Q: 录音没有声音输入

```bash
# 列出音频设备
python -c "import sounddevice as sd; print(sd.query_devices())"
```

检查：
- 麦克风是否正确连接
- 系统麦克风权限是否授权

### Q: AI 回复为空

1. 检查 LLM API 余额
2. 检查网络连接
3. 检查模型是否可用

### Q: 语音识别失败

1. 确认使用 16000 Hz 采样率
2. 检查阿里云 API 余额
3. 确认已开通语音识别服务

### Q: 本地模型加载失败

1. 确认 Python 版本 >= 3.10
2. 确认已安装 `litert-lm-api-nightly`
3. 检查模型文件路径是否正确
4. 确认模型文件完整（~2.4GB）

### Q: uv 安装依赖失败

1. 确认 Python 版本 >= 3.10
2. 尝试清除缓存：`uv cache clean`
3. 检查网络连接

---

## 部署

### 部署到服务器

```bash
# 1. 复制项目文件
scp -r voice-assistant-ai user@server:~/

# 2. 安装 uv
ssh user@server
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 安装依赖
cd voice-assistant-ai
uv venv
source .venv/bin/activate
uv pip install -e .

# 4. 配置 .env
cp .env.example .env
nano .env

# 5. 运行
python voice_assistant_ai.py
```

### Docker 部署（可选）

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制项目文件
COPY . .

# 安装依赖
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e .

CMD [".venv/bin/python", "voice_assistant_ai.py"]
```

---

## 后续开发

### 建议功能

1. **Web界面**: 添加 Gradio 或 Flask Web UI
2. **多语言支持**: 扩展支持英文、日文等
3. **离线 ASR**: 使用 Whisper 等本地 ASR 模型
4. **打断功能**: 语音打断助手说话
5. **多轮对话**: 更复杂的对话管理
6. **技能插件**: 可扩展的技能系统
7. **更多本地模型**: 支持其他 LiteRT-LM 兼容模型