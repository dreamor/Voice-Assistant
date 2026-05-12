# 模块说明

## 项目结构

```
voice-assistant/
├── src/voice_assistant/
│   ├── __main__.py              # 入口：启动 Web UI
│   ├── db.py                    # SQLite 对话历史
│   ├── config/                  # 配置加载
│   │   └── __init__.py          # AppConfig + ProviderConfig + 自定义 Provider 读写
│   ├── audio/
│   │   ├── cloud_asr.py         # 云端 ASR（DashScope Paraformer）
│   │   ├── funasr_asr.py        # 本地 FunASR
│   │   └── tts.py               # TTS Provider（EdgeTTS + 流式）
│   ├── core/
│   │   ├── session.py           # VoiceSession（process_text_stream / synthesize_stream）
│   │   ├── ai_client.py         # AI 对话客户端
│   │   ├── model_manager.py     # Provider / 模型故障转移
│   │   └── dependencies.py      # 依赖检查
│   ├── agent/
│   │   ├── orchestrator.py      # Agent Loop
│   │   └── llm_client.py        # Function Calling 通信层
│   ├── executors/
│   │   ├── base.py
│   │   ├── chat.py
│   │   ├── computer.py
│   │   └── interpreter.py
│   ├── model/
│   │   └── intent.py
│   ├── services/
│   │   └── router.py
│   ├── security/
│   │   ├── validation.py
│   │   └── safe_guard.py
│   ├── tools/
│   │   ├── registry.py
│   │   ├── universal/
│   │   └── platform_specific/
│   └── platform/
├── web_ui.py                    # FastAPI + WebSocket
├── web_static/                  # Web 前端
├── config.yaml
├── config/
│   ├── hotwords.json
│   └── custom_providers.yaml    # Web UI 写入
└── tests/
```

## 入口

### `voice_assistant.__main__`

```bash
python -m voice_assistant            # 启动 Web UI (127.0.0.1:8000)
python -m voice_assistant --check    # 依赖检查
```

只做一件事：启动 uvicorn 加载 `web_ui:app`。

## 音频模块 (`audio/`)

| 文件 | 说明 |
|------|------|
| `cloud_asr.py` | DashScope Paraformer 实时 ASR，提供 `recognize_bytes()` |
| `funasr_asr.py` | 本地 FunASR Paraformer-zh |
| `tts.py` | `TTSProvider` Protocol + `EdgeTTSProvider`（含 `synthesize_stream()` 分句流式） |

注：旧版的 `vad.py` 与 `player.py` 已移除。VAD 现在由浏览器 MediaRecorder + 能量阈值在前端 `web_static/js/audio.js` 实现；播放由浏览器 `AudioContext` + `StreamingAudioPlayer` 负责。

## 核心模块 (`core/`)

| 文件 | 说明 |
|------|------|
| `session.py` | `VoiceSession`：统一入口 `process_text()` / `process_text_stream()` / `synthesize_stream()` / `get_history()` |
| `ai_client.py` | LLM 流式调用封装 |
| `model_manager.py` | Provider + 模型队列，故障时自动 advance |
| `dependencies.py` | 启动前依赖检查 |

## Agent 模块 (`agent/`)

| 文件 | 说明 |
|------|------|
| `orchestrator.py` | `run_stream()` 生成 `AgentEvent`（llm_token / tool_start / tool_result / complete / error） |
| `llm_client.py` | `call_llm_with_tools_stream()` 基于 litellm，统一 OpenAI / Anthropic / DashScope 等 |

## 执行器 (`executors/`)

`ChatExecutor` / `ComputerExecutor` / `InterpreterExecutor`。Router 根据意图路由。

## 工具系统 (`tools/`)

- `registry.py`: `@register_tool` 装饰器、`ToolResult` 数据类、参数校验
- `universal/`: 文件、剪贴板、屏幕、键鼠输入
- `platform_specific/`: 按系统注册（macOS / Windows / Linux）

## 安全 (`security/`)

- `validation.py`: 输入边界校验
- `safe_guard.py`: 分级拦截（auto / confirm / double_confirm / blocked）

## 数据库 (`db.py`)

SQLite，表：`conversations` / `messages`。

主要函数：

```python
create_conversation(title)             # -> id
save_message(conv_id, role, content)
get_conversation_history(conv_id, limit)
get_history(limit)                     # 列表
delete_conversation(conv_id)
delete_conversations(ids)              # 批量
clear_history()
```

## 配置 (`config/__init__.py`)

- `AppConfig` / `ASRConfig` / `LLMConfig` / `ProviderConfig` / `ProvidersConfig` 等 dataclass
- `load_config()`: 读取 `config.yaml` + `.env`，合并 `config/custom_providers.yaml`
- `save_custom_provider(...)`: Web UI 新增 Provider 时写入 `config/custom_providers.yaml`
- `delete_custom_provider(id)`: 删除
- `_validate_config(cfg)`: 启动时校验

## Web 层

| 文件 | 说明 |
|------|------|
| `web_ui.py` | FastAPI 路由：`/api/config` `/api/providers` `/api/providers/create` `/api/history/batch-delete` `/ws/{client_id}` |
| `web_static/js/app.js` | 入口 + 事件绑定 |
| `web_static/js/api.js` | REST 封装 |
| `web_static/js/ws.js` | WebSocket 消息收发 |
| `web_static/js/audio.js` | 录音 + `StreamingAudioPlayer`（逐句播放 TTS chunk） |
| `web_static/js/ui.js` | 列表渲染、批量选择、消息流式渲染 |
| `web_static/js/config.js` | 配置页 + Provider 管理 |
| `web_static/js/state.js` | 全局状态（`conversationId` / `isSelectMode` / `selectedConversationIds` / `providers` ...） |

Web UI 与 `VoiceSession` 是唯一数据通路，不再绕过 Session 直接调用底层模块。
