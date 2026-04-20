# 系统架构

## 概述

语音助手是一个端到端的中文语音交互系统，采用现代化的执行器架构设计。

**核心特性**：
- **智能意图识别**：自动判断用户意图，路由到对应执行器
- **Open Interpreter 集成**：真正的 Open Interpreter 库，强大的电脑控制能力
- **双模式处理**：自动模式（意图识别）和 AI 对话模式
- **本地/在线 LLM 切换**：支持离线运行，隐私保护
- **对话上下文**：支持多轮对话，保持上下文

## 系统架构图

### 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              用户交互层                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   Web UI    │  │   麦克风     │  │   扬声器     │  │   控制台     │  │
│  │ (浏览器界面) │  │             │  │             │  │  (CLI)      │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                │                │         │
│         ▼                ▼                ▼                ▼         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     Web UI 服务 (web_ui.py)                       │  │
│  │         FastAPI + WebSocket + 静态文件服务                        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│         │                                                              │
│         │ WebSocket / REST API                                         │
│         ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │              主程序 (voice_assistant/main.py)                     │  │
│  │         流程控制 + 状态管理 + LLM模式切换 + 日志记录              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   VAD 录音    │    │  语音识别    │    │   音频播放   │
│   (vad.py)   │    │(cloud_asr.py)│    │(audio_player)│
└──────────────┘    └──────────────┘    └──────────────┘
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ sounddevice  │    │ 阿里云 Dash  │    │   pygame     │
│  实时录音    │    │  Scope ASR   │    │   播放       │
└──────────────┘    └──────────────┘    └──────────────┘

                        核心处理层
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     意图识别 + 路由                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ LLM 分类器   │→ │ CommandRouter│← │  Intent      │         │
│  │(云端LLM优先) │  │ (路由器)     │  │ (数据类)     │         │
│  └──────┬───────┘  └──────────────┘  └──────────────┘         │
│         │ fallback                                             │
│  ┌──────┴───────┐                                              │
│  │ 关键词匹配   │ (LLM 不可用/低置信度时兜底)                   │
│  └──────────────┘                                              │
                              │
       ┌──────────────────────┴──────────────────────┐
       │                                             │
       ▼                                             ▼
┌──────────────────┐                    ┌──────────────────┐
│ ComputerExecutor │                    │  ChatExecutor    │
│  (电脑控制)       │                    │   (对话处理)      │
│                  │                    │                  │
│ ┌──────────────┐ │                    │ ┌──────────────┐ │
│ │Interpreter   │ │                    │ │ ai_client.py │ │
│ │Executor      │ │                    │ │ ask_ai_stream│ │
│ │(Open Int.)   │ │                    │ └──────────────┘ │
│ └──────────────┘ │                    │                  │
└──────────────────┘                    └──────────────────┘
       │                                             │
       ▼                                             ▼
┌──────────────────┐                    ┌──────────────────┐
│ Open Interpreter │                    │  LLM (本地/在线) │
│  代码生成与执行   │                    │   对话生成       │
└──────────────────┘                    └──────────────────┘
                                                │
                                     ┌──────────┴──────────┐
                                     │                     │
                                     ▼                     ▼
                              ┌──────────────┐    ┌──────────────┐
                              │  本地模型     │    │  在线 API    │
                              └──────────────┘    └──────────────┘
```

## 核心组件

### 1. 配置模块 (config/)

**文件**: `config/__init__.py`, `config.yaml`

**职责**:
- 从 `config.yaml` 加载应用配置
- 从 `.env` 加载敏感信息（API Key）
- 提供统一的配置访问接口

**配置结构**:
```python
AppConfig
├── name: str
├── version: str
├── asr: ASRConfig
├── llm: LLMConfig
│   └── local: LocalLLMConfig
│       └── use_multimodal_audio: bool
├── audio: AudioConfig
├── vad: VADConfig
├── interpreter: InterpreterConfig
├── history: HistoryConfig
├── intent: IntentConfig    # LLM 意图识别配置
└── logging: LoggingConfig
```

### 2. 数据模型 (models/)

**文件**: `models/intent.py`

**Intent 数据类**:
```python
@dataclass(frozen=True)
class Intent:
    intent_type: IntentType         # 意图类型
    original_text: str              # 用户原始输入
    slots: dict[str, Any]           # 槽位信息
    confidence: float               # 置信度
    code_to_execute: Optional[str]  # 待执行代码（电脑控制）
    language: Optional[str]         # 代码语言
```

**意图类型**:
| 类型 | 说明 | 执行器 |
|------|------|--------|
| `COMPUTER_CONTROL` | 电脑操作 | ComputerExecutor |
| `ORDINARY_CHAT` | 普通对话 | ChatExecutor |
| `QUERY_ANSWER` | 问答查询 | ChatExecutor |

### 3. 执行器模块 (executors/)

**基类**: `BaseExecutor`
```python
class BaseExecutor(ABC):
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        pass

    @abstractmethod
    def can_handle(self, intent_type: str) -> bool:
        pass
```

**ComputerExecutor** - 电脑控制执行器：
- 使用 Open Interpreter 库
- 支持自然语言转代码
- 自动执行生成的 Python/Bash 代码
- 返回执行结果

**ChatExecutor** - 对话执行器：
- 处理普通对话和问答
- 维护对话历史
- 流式 LLM 响应
- 限制响应长度（适合 TTS）

### 4. 路由服务 (services/)

**文件**: `services/router_service.py`

**CommandRouter** - 命令路由器：
```python
class CommandRouter:
    def __init__(self, executors: list[BaseExecutor]):
        self.executors = executors

    def route(self, intent: Intent, context: dict = None) -> dict:
        # 根据意图类型路由到对应执行器
        for executor in self.executors:
            if executor.can_handle(intent.intent_type.value):
                return executor.execute(**kwargs)
```

**简单分类器** - `simple_classify_intent()`:
- 基于关键词匹配
- 快速判断意图类型
- 返回 Intent 对象

### 5. Open Interpreter 执行器

**文件**: `interpreter_executor.py`

**职责**:
- 封装 Open Interpreter 库
- 配置 LLM 模型和 API
- 支持本地模型（通过 Ollama）
- 执行用户命令
- 提取友好的响应文本

**使用示例**:
```python
executor = InterpreterExecutor(auto_run=True, verbose=False)
result = executor.execute("打开 Chrome 浏览器")
print(result["response"])
```

### 6. 本地 LLM 模块


**职责**:
- 提供与在线 LLM 兼容的接口
- 支持流式输出
- 管理对话上下文

**使用示例**:
```python
with LocalLLMClient("model.litertlm") as client:
    for chunk in client.ask_stream("你好"):
        print(chunk, end='')
```

### 7. 语音识别 (ASR)

**文件**: `cloud_asr.py`

**功能**: 将音频转换为文本
**服务**: 阿里云 DashScope Paraformer
**优化**: 热词支持、中英文混合、语气词过滤

### 8. 语音活动检测 (VAD)

**文件**: `vad.py`

**功能**: 实时监测麦克风输入，自动检测说话开始和结束
**技术**: 基于 RMS 能量阈值的声音检测

### 9. 语音合成 (TTS)

**文件**: `tts.py`

**服务**: Microsoft Edge-TTS
**功能**: 将文本合成为语音

### 10. 音频播放

**文件**: `audio_player.py`

**技术**: pygame
**功能**: 播放 TTS 生成的音频

### 11. 安全工具

**文件**: `security_utils.py`

**功能**:
- 输入验证（文本、音频）
- 速率限制
- 安全常量定义

## 工作流程

### 自动模式（默认）

```
1. 用户按 Enter 开始录音
   │
   ▼
2. VAD 模块监听麦克风
   - 检测到声音 → 开始录音
   - 静默超时 → 停止录音
   │
   ▼
3. 保存音频为 WAV 格式
   │
   ▼
4a. 多模态路径（本地模型 + 多模态开启）:
    音频直接送 Gemma 4 → 得到回复文本 → 跳至步骤 6
4b. 传统路径（默认）:
    云端 ASR 识别音频为文本
    │
    ▼
   5. ASR 纠错（可选）
   │
   ▼
6. 意图分类器判断类型
   │
   ├── LLM 分类（云端 qwen-turbo，语义理解）
   │   └── 低于 0.3 置信度 → 回退到关键词匹配
   ├── 关键词匹配（兜底）
   │   ├── 包含操作关键词 → COMPUTER_CONTROL
   │   ├── 包含问号 → QUERY_ANSWER
   │   └── 其他 → ORDINARY_CHAT
   │
   ▼
7. CommandRouter 路由到对应执行器
   │
   ├── ComputerExecutor → Open Interpreter 执行
   │   ├── LLM 解析意图
   │   ├── 生成 Python/Bash 代码
   │   ├── 执行代码
   │   └── 返回结果
   │
   └── ChatExecutor → LLM 对话
       ├── 多模态路径: 使用 direct_response 跳过二次 LLM
       ├── 传统路径: 调用云端/本地 LLM
       ├── 构建对话历史
       └── 返回回复
   │
   ▼
8. TTS 将文本合成为语音
   │
   ▼
9. 播放器输出到扬声器
   │
   ▼
10. 等待用户下一轮输入
```

### AI 对话模式

```
用户输入 → ASR → ChatExecutor → LLM 对话 → TTS → 播放
```

### LLM 模式切换

```
按 L 键 → toggle_llm_mode()
        │
        ├── 切换到本地模式
        │   ├── 初始化 LocalLLMClient
        │
        └── 切换到在线模式
            ├── 关闭 LocalLLMClient
            └── 使用 DashScope API
```

## 配置管理

### config.yaml（非敏感配置）

```yaml
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
  local:

interpreter:
  auto_run: true
  verbose: false
```

### .env（敏感信息）

```ini
ASR_API_KEY=your-asr-api-key
LLM_API_KEY=your-llm-api-key
```

## Web UI 架构

Web UI 采用 **FastAPI + WebSocket + Vanilla JS** 架构：

```
┌─────────────────────────────────────────────────────────────┐
│                        浏览器前端                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  index.html  │  │   style.css  │  │    app.js    │       │
│  │   页面结构   │  │   样式主题   │  │  交互逻辑    │       │
│  └──────┬───────┘  └──────────────┘  └──────┬───────┘       │
│         │                                    │                │
│         └────────────────────────────────────┘                │
│                          │                                   │
│                    WebSocket / HTTP                          │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────┐
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              FastAPI 后端 (web_ui.py)                    │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  REST API:                                              │ │
│  │    GET  /api/config          获取配置                  │ │
│  │    POST /api/config          更新配置                  │ │
│  │    GET  /api/models          获取可用模型列表          │ │
│  │    GET  /api/history         获取对话历史              │ │
│  │    POST /api/history/clear   清除对话历史              │ │
│  │                                                         │ │
│  │  WebSocket:                                             │ │
│  │    /ws/chat                实时聊天连接                │ │
│  │                                                         │ │
│  │  静态文件:                                              │ │
│  │    /                       主页面 (index.html)        │ │
│  │    /style.css              样式文件                    │ │
│  │    /app.js                 前端脚本                    │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Web UI 组件说明

| 组件 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Vanilla JS | 无框架依赖，轻量快速 |
| 后端框架 | FastAPI | 高性能异步 Web 框架 |
| 实时通信 | WebSocket | 全双工通信，支持流式响应 |
| 数据存储 | SQLite | 本地对话历史存储 |
| 音频处理 | Web Audio API + MediaRecorder | 浏览器原生录音 |
| 样式设计 | CSS Custom Properties | 支持主题切换 |

### Web UI 工作流程

```
1. 用户打开浏览器访问 http://127.0.0.1:8000
   │
   ▼
2. FastAPI 返回静态页面 (index.html + style.css + app.js)
   │
   ▼
3. 前端建立 WebSocket 连接 (/ws/chat)
   │
   ▼
4. 用户点击录音按钮
   - 使用 MediaRecorder API 录制音频
   - 录制完成后转为 Base64
   - 通过 WebSocket 发送到后端
   │
   ▼
5. 后端处理
   - 解码 Base64 音频
   - ASR 语音识别 → 文本
   - LLM 对话生成 → 流式响应
   - TTS 语音合成 → 音频
   │
   ▼
6. 前端接收并展示
   - 实时显示 AI 文本回复（流式）
   - 自动播放 TTS 音频
   - 保存到对话历史
```

## 技术栈

| 类别 | 技术 |
|------|------|
| 编程语言 | Python 3.10+ |
| Web 框架 | FastAPI |
| 实时通信 | WebSocket |
| 前端 | Vanilla JavaScript |
| 数据库 | SQLite |
| 语音识别 | 阿里云 DashScope (Paraformer) / FunASR |
| LLM（在线） | 阿里云百炼 |
| 语音合成 | Microsoft Edge-TTS |
| 音频录制 | sounddevice / Web MediaRecorder API |
| 音频播放 | pygame / Web Audio API |
| 音频处理 | soundfile, numpy |
| 配置管理 | python-dotenv, PyYAML |
| 电脑控制 | Open Interpreter |
| 包管理 | uv |

## 架构优势

1. **模块化设计**: 各组件职责清晰，易于维护和扩展
2. **执行器模式**: 统一的接口设计，便于添加新的执行器类型
3. **意图驱动**: 基于意图分类的自动路由，用户体验更流畅
4. **配置分离**: 敏感信息与非敏感配置分离，更安全
5. **本地/在线双模式**: 支持离线运行，保护隐私
6. **真正的 Open Interpreter**: 使用官方库，获得完整的电脑控制能力

## 扩展点

1. **添加新的执行器**: 继承 `BaseExecutor` 实现新类型
2. **意图分类器**: 可替换为 LLM 分类或其他 ML 模型
3. **ASR 引擎**: 可替换为 Whisper 等其他服务
4. **TTS 引擎**: 可替换为 Azure TTS 等其他服务
6. **宏命令系统**: 添加 MacroExecutor 支持预设操作序列