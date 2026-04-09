# 开发指南

## 环境准备

### 1. 安装 Python 依赖

```bash
# 克隆或下载项目代码
cd voice-assistant-ai

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制配置示例
cp .env.sample .env

# 编辑 .env 填入 API 密钥
# 必须填写:
# - ASR_API_KEY (语音识别)
# - LLM_API_KEY (AI 对话)
```

### 3. 验证环境

```bash
# 运行测试
pytest test_system.py -v

# 测试单个模块
python -c "from vad import record_audio; print('VAD OK')"
python -c "from tts import synthesize; print('TTS OK')"
python -c "from ai_client import ask_ai_stream; print('AI OK')"
```

---

## 运行

### 启动语音助手

```bash
python voice_assistant_ai.py
```

### 交互控制

```
[ENTER=Record / C=Clear / H=History / I=Toggle / Q=Quit] (模式:Interpreter):
```

| 按键 | 功能 |
|------|------|
| Enter | 开始录音（VAD自动检测说话） |
| C | 清除对话历史 |
| H | 显示对话历史 |
| I | 切换 Interpreter/AI 模式 |
| Q | 退出程序 |

---

## 开发

### 代码结构

```
voice_assistant/
├── voice_assistant_ai.py   # 主程序
├── cloud_asr.py            # 语音识别
├── vad.py                  # 语音检测
├── tts.py                  # 语音合成
├── ai_client.py            # AI对话
├── audio_player.py         # 音频播放
├── test_system.py          # 测试用例
├── requirements.txt        # 依赖
├── .env                    # 配置（需创建）
└── docs/                   # 文档
```

### 模块开发

#### 添加新的 ASR 引擎

```python
# 1. 创建新模块 asr_new.py
class NewASR:
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def recognize_from_bytes(self, audio_bytes, sample_rate=44100):
        # 实现识别逻辑
        result = do_recognize(audio_bytes)
        return result

# 2. 修改 main.py 导入
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

# 2. 修改 main.py 导入
from tts_new import synthesize
```

### 调试

#### 本地测试 VAD

```python
from vad import record_audio, calculate_rms
import numpy as np

# 测试 RMS 计算
test_audio = np.random.randn(44100) * 0.1
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

for response in ask_ai_stream("你好"):
    print(response, end='')
```

---

## 测试

### 运行全部测试

```bash
pytest test_system.py -v
```

### 运行特定测试

```bash
# 只测试配置
pytest test_system.py::TestConfiguration -v

# 只测试 ASR
pytest test_system.py::TestCloudASR -v
```

### 测试覆盖

- `TestImports`: 依赖包导入
- `TestConfiguration`: 配置加载
- `TestOpenRouterAPI`: API 连接
- `TestCloudASR`: 语音识别
- `TestEdgeTTS`: 语音合成
- `TestAudioDevices`: 音频设备
- `TestVoiceAssistantAI`: 主模块

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

1. 检查 OpenRouter API 余额
2. 检查网络连接
3. 检查模型是否可用

### Q: 语音识别失败

1. 确认使用 44100 Hz 采样率
2. 检查阿里云 API 余额
3. 确认已开通语音识别服务

---

## 输出构建产物

项目为纯 Python 脚本，无需编译。

### 部署到服务器

```bash
# 1. 复制项目文件
scp -r voice_assistant-ai user@server:~/

# 2. 安装依赖
ssh user@server
cd voice-assistant-ai
pip install -r requirements.txt

# 3. 配置 .env
cp .env.sample .env
nano .env

# 4. 运行
python voice_assistant_ai.py
```

---

## 后续开发

### 建议功能

1. **Web界面**: 添加 Gradio 或 Flask Web UI
2. **多语言支持**: 扩展支持英文、日文等
3. **离线模式**: 使用本地 ASR/TTS 模型
4. **打断功能**: 语音打断助手说话
5. **多轮对话**: 更复杂的对话管理
6. **技能插件**: 可扩展的技能系统