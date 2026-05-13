# 模块说明

## 项目结构

```
voice-assistant/
├── src/voice_assistant/
│   ├── __main__.py              # 入口：启动 Web UI
│   ├── db.py                    # SQLite 对话历史
│   ├── config/                  # 配置加载 + 自定义 Provider 持久化
│   ├── audio/
│   │   ├── cloud_asr.py         # 云端 ASR（DashScope Paraformer）
│   │   ├── funasr_asr.py        # 本地 FunASR
│   │   ├── asr_provider.py      # ASR 注册表
│   │   └── tts.py               # TTS Provider（EdgeTTS + 流式）
│   ├── core/
│   │   ├── session.py           # VoiceSession 统一入口
│   │   ├── model_manager.py     # Provider / 模型故障转移
│   │   ├── asr_corrector.py     # LLM 语境纠错
│   │   └── dependencies.py      # 依赖检查
│   ├── agent/
│   │   ├── orchestrator.py      # Agent Loop（run / run_stream）
│   │   └── llm_client.py        # Function Calling 通信层（litellm）
│   ├── security/
│   │   ├── validation.py        # 输入边界 + 速率限制
│   │   └── safe_guard.py        # 工具分级拦截
│   ├── tools/
│   │   ├── registry.py          # @register_tool + ToolResult + 参数校验
│   │   ├── universal/           # 文件 / 剪贴板 / 屏幕 / 输入 / 系统 / 实用
│   │   └── platform_specific/   # mac_ops.py / win_ops.py
│   └── platform/                # detect_platform + MacAdapter / WindowsAdapter
├── web_ui.py                    # FastAPI + WebSocket
├── web_static/                  # Web 前端 ES Module
├── config.yaml                  # 内置配置 + 内置 Provider
├── config/
│   ├── hotwords.json
│   └── custom_providers.yaml    # Web UI 写入的自定义 Provider
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
| `cloud_asr.py` | DashScope Paraformer 实时 ASR，含 `HotwordsManager`，提供 `recognize_bytes()` |
| `funasr_asr.py` | 本地 FunASR Paraformer-zh |
| `asr_provider.py` | ASR Protocol + 注册表，`create_asr_provider(config)` 按配置返回实例 |
| `tts.py` | `TTSProvider` Protocol + `EdgeTTSProvider`（含 `synthesize_stream()` 分句流式） |

注：旧版的 `vad.py` 与 `player.py` 已移除。VAD 由浏览器 MediaRecorder + 能量阈值在前端 `web_static/js/audio.js` 实现；播放由浏览器 `AudioContext` + `StreamingAudioPlayer` 负责。

## 核心模块 (`core/`)

| 文件 | 说明 |
|------|------|
| `session.py` | `VoiceSession` 统一入口：`process_text()` / `process_text_stream()` / `recognize()` / `synthesize()` / `synthesize_stream()` / `get_history()` |
| `model_manager.py` | Provider + 模型队列，HTTP 429/5xx 故障时自动切换备用模型 |
| `asr_corrector.py` | 用 LLM 对 ASR 结果做语境纠错（如「open interpreter」→「Open Interpreter」） |
| `dependencies.py` | 启动前依赖检查 |

## Agent 模块 (`agent/`)

| 文件 | 说明 |
|------|------|
| `orchestrator.py` | `run()` / `run_stream()`，生成 `AgentEvent`（llm_token / tool_start / tool_result / complete / error） |
| `llm_client.py` | `call_llm_with_tools_stream()`，基于 litellm 统一 OpenAI / Anthropic / DashScope / DeepSeek 等 |

**关键设计**：Agent Loop 是唯一执行路径。LLM 自己决定是否调 tool；不调则直接生成回答（覆盖纯对话场景）。无独立 router / chat executor 分支。

## 工具系统 (`tools/`)

- `registry.py`: `@register_tool` 装饰器、`ToolResult` 数据类、参数校验、平台过滤
- `universal/`: 文件、剪贴板、屏幕、键鼠输入、系统、实用工具
- `platform_specific/`: 按系统加载 `mac_ops.py` / `win_ops.py`

工具自动注册到 `ToolRegistry`，通过 `get_openai_tools()` 暴露给 LLM 做 function calling。

## 安全 (`security/`)

- `validation.py`: 输入边界校验 + 速率限制（`RateLimiter`）
- `safe_guard.py`: 分级拦截（`auto` / `confirm` / `double_confirm` / `blocked`）

每个 tool 定义 `safety_level`，Orchestrator 执行前先过 SafeGuard；`confirm` 级别会通过 WebSocket 推送 `confirm_request` 给前端，等待用户响应。

## 平台 (`platform/`)

- `detect_platform()`: 返回 `"mac"` / `"windows"` / `"linux"`
- `MacAdapter` / `WindowsAdapter`: 抽象统一的 `open_file` / `open_url` / `run_script` 等接口

## 数据库 (`db.py`)

SQLite，表：`conversations` / `messages`。

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
- `save_custom_provider(...)` / `update_custom_provider(...)`: Web UI 写入 / 更新
- `delete_custom_provider(id)`: 删除
- `_validate_config(cfg)`: 启动时校验

## Web 层

| 文件 | 说明 |
|------|------|
| `web_ui.py` | FastAPI 路由：`/api/config` `/api/providers` `/api/providers/create` `/api/providers/{id}` (PATCH/DELETE) `/api/history/batch-delete` `/ws/{client_id}` |
| `web_static/js/app.js` | 入口 + 事件绑定 |
| `web_static/js/api.js` | REST 封装 |
| `web_static/js/ws.js` | WebSocket 消息收发 |
| `web_static/js/audio.js` | 录音 + `StreamingAudioPlayer`（逐句播放 TTS chunk） |
| `web_static/js/ui.js` | 列表渲染、批量选择、消息流式渲染 |
| `web_static/js/config.js` | 配置页 + Provider 管理（含 base_url 编辑、模型增删） |
| `web_static/js/state.js` | 全局状态 |

Web UI 与 `VoiceSession` 是唯一数据通路。
