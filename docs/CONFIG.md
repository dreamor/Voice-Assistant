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
| `LLM_API_KEY` | ✅ | **序号**（1-N），指向 config.yaml 中 providers 的第几个 |
| `ASR_API_KEY` | ✅ | 语音识别 API 密钥（DashScope Paraformer） |
| `DASHSCOPE_API_KEY` | 用 dashscope 时 | dashscope provider 的 LLM Key |
| `OPENAI_API_KEY` | 用 openai 时 | openai provider 的 Key |
| `ANTHROPIC_API_KEY` | 用 anthropic 时 | anthropic provider 的 Key |
| `DEEPSEEK_API_KEY` | 用 deepseek 时 | deepseek provider 的 Key |
| `{PROVIDER_ID}_API_KEY` | 自定义 | 自定义 provider，按 ID 推导命名 |

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
    vocabulary_id: ""                # 由 register_hotwords.py 注册后填入
    config_file: "config/hotwords.json"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `model` | ASR 模型 | paraformer-realtime-v2 |
| `base_url` | ASR 服务地址 | https://dashscope.aliyuncs.com/api/v1 |
| `language_hints` | 语言提示 | ["zh", "en"] |
| `disfluency_removal_enabled` | 过滤语气词 | true |
| `max_sentence_silence` | 句间停顿容忍(ms) | 1200 |
| `hotwords.enabled` | 启用热词 | false (阿里云免费配额已用完) |
| `hotwords.vocabulary_id` | 已注册的热词列表 ID，留空则首次启动自动创建 | "" |
| `hotwords.config_file` | 热词配置文件 | config/hotwords.json |

**热词注册流程**（启用 `hotwords.enabled` 后）：

```bash
# 1. 编辑 config/hotwords.json，写入业务相关词表
# 2. 注册到 DashScope，拿到 vocabulary_id
python scripts/register_hotwords.py
# 3. 把打印出的 ID 填到 config.yaml 的 asr.hotwords.vocabulary_id
```

辅助工具：

| 脚本 | 用途 |
|------|------|
| `scripts/register_hotwords.py` | 注册 `config/hotwords.json` 到 DashScope，输出 `vocabulary_id` |
| `scripts/list_hotwords.py` | 列出账号下已注册的热词列表（`--match` 与本地比对） |
| `scripts/cleanup_hotwords.py` | 清理冗余的旧热词列表，避免配额超限 |

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
  local:
    system_prompt: "你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `model` | AI 模型（在线） | kimi-k2.5 |
| `base_url` | LLM 服务地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| `max_tokens` | 最大响应长度 | 2000 |
| `temperature` | 创造性程度 | 0.7 |
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

### 音频配置

```yaml
audio:
  sample_rate: 16000
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `sample_rate` | 采样率 (Hz) | 16000 |

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

> 已废弃；旧版本配置项保留兼容，新版本不再读取。可从 yaml 删除该节。

### Agent 配置

```yaml
agent:
  max_iterations: 5          # Agent 循环最大迭代次数
  confirmation_timeout: 60   # 确认等待超时（秒）
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `max_iterations` | Agent 循环最大迭代次数 | 5 |
| `confirmation_timeout` | 用户确认等待超时时间（秒） | 60 |

**安全等级**：

| 等级 | GuardAction | 行为 |
|------|-------------|------|
| `READ_ONLY` | APPROVED | 自动执行，无需确认 |
| `WRITE` | CONFIRM_NEEDED | 需要用户单次确认 |
| `DANGEROUS` | DOUBLE_CONFIRM | 需要用户二次确认 |
| `BLOCKED` | BLOCKED | 阻止执行 |

**Tools 配置**：

```yaml
tools:
  blocked: []  # 被阻止的工具名称列表，如 ["run_python_code"] 完全禁用代码执行
  overrides: []  # 工具安全级别覆盖，例如：
    # - name: run_python_code
    #   level: blocked          # 完全禁用
    # - name: write_file
    #   level: dangerous        # 升级为二次确认
```

**`run_python_code` 默认行为**：

DANGEROUS 级别，每次执行都需要用户二次确认；30 秒超时（最大 120 秒）；在独立子进程中运行，cwd 默认为用户 home 目录；stdout/stderr 输出超过 8KB 时尾部截断。如完全不需要，可在 `tools.blocked` 中加入 `run_python_code`。

---

## 本地 ASR 配置

### 启用 FunASR

```bash
uv pip install -e ".[local-asr]"
```

```yaml
# config.yaml
asr:
  use_local: true
  local:
    enabled: true
    model_path: null   # null = 自动下载 Paraformer-zh
    device: "cpu"      # 或 "cuda"
    vad_threshold: 0.5
```

首次启动自动下载至 `~/.cache/modelscope/hub/`（约 2GB）。

### Provider 切换

- 启动后在 Web UI 配置页切换 Provider 与模型
- 自定义 Provider 通过「添加 Provider」写入 `config/custom_providers.yaml`

---

## 完整配置示例

### .env

```env
# 敏感配置 - 不要提交到版本控制
ASR_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# LLM_API_KEY = 序号，指向 config.yaml 中 providers 的第几个
LLM_API_KEY=1

# Provider Keys（用哪个就填哪个）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
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
  model: "qwen3-coder-plus-2025-09-23"
  max_tokens: 2000
  temperature: 0.7
# 当前活跃 provider 由 .env 中 LLM_API_KEY 决定（值为下方 providers 的序号）

providers:
  dashscope:
    name: "阿里云 DashScope"
    litellm_prefix: "openai"
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key_env: "DASHSCOPE_API_KEY"
    models:
      - id: "qwen3-coder-plus-2025-09-23"
        name: "Qwen3 Coder Plus"
      - id: "qwen-plus-latest"
        name: "Qwen Plus"

audio:
  sample_rate: 16000

tts:
  provider: "edge-tts"
  voice: "zh-CN-XiaoxiaoNeural"

vad:
  threshold: 0.02
  silence_timeout: 1.5
  min_speech: 0.15
  wait_timeout: 10
  max_recording: 30

history:
  max_turns: 20

logging:
  level: "INFO"
  format: "%(asctime)s - %(levelname)s - %(message)s"

agent:
  max_iterations: 5
  confirmation_timeout: 60
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