# 配置说明

## 配置文件

项目使用 `.env` 文件管理配置，需要从示例文件复制并填入自己的API密钥。

### 创建配置

```bash
cp .env.sample .env
# 编辑 .env 填入 API Key
```

---

## ASR 配置 (语音识别)

| 变量名 | 必填 | 说明 | 默认值 |
|--------|------|------|--------|
| `ASR_API_KEY` | ✅ | ASR 服务 API 密钥 | - |
| `ASR_MODEL` | | ASR 模型 | paraformer-realtime-v2 |
| `ASR_BASE_URL` | | ASR 服务地址 | https://dashscope.aliyuncs.com/api/v1 |

### 当前使用阿里云 DashScope

1. 访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)
2. 注册/登录阿里云账号
3. 开通语音识别服务
4. 在「API-KEY管理」中创建 API Key

### 可用模型

| 模型 | 说明 |
|------|------|
| `paraformer-realtime-v2` | Paraformer 实时语音识别 v2 (推荐) |
| `paraformer-realtime-8k-v2` | 实时识别，8kHz采样率 |

---

## LLM 配置 (AI 对话)

| 变量名 | 必填 | 说明 | 默认值 |
|--------|------|------|--------|
| `LLM_API_KEY` | ✅ | LLM 服务 API 密钥 | - |
| `LLM_MODEL` | | AI 模型 | kimi-k2.5 |
| `LLM_BASE_URL` | | LLM 服务地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |

### 当前使用阿里云百炼

1. 访问 [阿里云百炼](https://bailian.console.aliyun.com/)
2. 获取 API Key（与 ASR 相同）

### 推荐模型

| 模型ID | 说明 | 特点 |
|--------|------|------|
| `kimi-k2.5` | Kimi K2.5 | 推荐使用 |
| `qwen-turbo` | Qwen Turbo | 免费 |
| `qwen-plus` | Qwen Plus | 更强能力 |

---

## 音频配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SAMPLE_RATE` | 采样率 (Hz) | 44100 |
| `EDGE_TTS_VOICE` | TTS音色 | zh-CN-XiaoxiaoNeural |

### 采样率说明

- `44100`: CD音质，推荐使用
- `16000`: 低采样率，文件更小
- `48000`: 高音质，文件更大

### Edge-TTS 可用音色

**中文音色:**

| 音色ID | 描述 |
|--------|------|
| `zh-CN-XiaoxiaoNeural` | 晓晓（女声）- 推荐 |
| `zh-CN-YunxiNeural` | 云希（男声） |
| `zh-CN-YunyangNeural` | 云扬（男声） |

**其他语言音色:**

| 音色ID | 语言 |
|--------|------|
| `en-US-JennyNeural` | 英语（女声） |
| `en-US-GuyNeural` | 英语（男声） |
| `ja-JP-NanamiNeural` | 日语（女声） |

---

## VAD 配置

| 变量名 | 说明 | 默认值 | 单位 |
|--------|------|--------|------|
| `VAD_THRESHOLD` | 声音检测阈值 | 0.02 | RMS能量 |
| `VAD_SILENCE_TIMEOUT` | 静默超时 | 1.5 | 秒 |
| `VAD_MIN_SPEECH` | 最小语音时长 | 0.3 | 秒 |
| `VAD_WAIT_TIMEOUT` | 等待超时 | 10 | 秒 |

### 参数调优

**VAD_THRESHOLD (灵敏度)**
- `0.01`: 非常灵敏，可能捕获背景噪音
- `0.02`: 默认值，正常环境
- `0.05`: 较不灵敏，需要较大声音
- `0.10`: 非常不灵敏，只响应大声

**VAD_SILENCE_TIMEOUT (停止延迟)**
- `1.0`: 快速响应，短停顿即停止
- `1.5`: 默认值，自然对话停顿
- `2.0`: 较长等待，允许思考停顿时

**VAD_MIN_SPEECH (最小录音)**
- 低于此长度的音频会被丢弃

---

## AI 配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SYSTEM_PROMPT` | 系统提示词 | 友好的中文语音助手 |

### SYSTEM_PROMPT 示例

```env
# 默认
SYSTEM_PROMPT=你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。每次回复控制在50字以内。

# 命令行助手
SYSTEM_PROMPT=你是一个命令行助手，可以用Python代码控制电脑执行各种操作。

# 专业助手
SYSTEM_PROMPT=你是一个专业的技术顾问，回答要详细准确。
```

---

## 完整配置示例

```env
# ========== ASR 配置 (语音识别) ==========
ASR_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
ASR_MODEL=paraformer-realtime-v2
ASR_BASE_URL=https://dashscope.aliyuncs.com/api/v1

# ========== LLM 配置 (AI 对话) ==========
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=kimi-k2.5
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# ========== 音频配置 ==========
SAMPLE_RATE=44100
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural

# ========== VAD 配置 ==========
VAD_THRESHOLD=0.02
VAD_SILENCE_TIMEOUT=1.5
VAD_MIN_SPEECH=0.3
VAD_WAIT_TIMEOUT=10

# ========== AI 配置 ==========
SYSTEM_PROMPT=你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。每次回复控制在50字以内。
```

---

## 环境验证

运行测试验证配置是否正确：

```bash
pytest test_system.py -v
```

测试会检查：
- 所有依赖包是否正确安装
- 配置项是否已设置
- API 密钥是否有效
- 音频设备是否可用