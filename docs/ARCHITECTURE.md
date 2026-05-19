# 系统架构

纯 Web 的中文语音助手，架构围绕**一条主路径**：

```
浏览器 (录音/文本) ──WS──▶ FastAPI (web_ui.py)
                              │
                              ▼
                        VoiceSession (core/session.py)
                              │
                              ├─ ASR  (audio/cloud_asr | funasr_asr)
                              │
                              ├─ AgentOrchestrator (agent/orchestrator.py)
                              │     │
                              │     ├─ LLM (agent/llm_client.py, litellm 流式 + tools)
                              │     ├─ ModelManager (core/model_manager.py, 故障切换)
                              │     ├─ ToolRegistry (tools/) + SafeGuard (security/)
                              │     └─ 循环：function call → tool → 结果回传 → 直到无 tool 或 stop
                              │
                              └─ TTS (audio/tts.py, 分句流式合成)
                                       │
                                       ▼
                              StreamingAudioPlayer (web_static/js/audio.js)
                                       │
                                       ▼
                                   浏览器播放
```

## 设计原则

- **单一路径**：所有用户输入（语音 / 文本）都走 Agent Loop。LLM 自己决定是否调 tool；不调则直接答（覆盖纯对话）。无独立 router / chat executor 分支。
- **流式优先**：LLM token / TTS 分句 / WebSocket 事件全程流式。
- **多 Provider 抽象**：DashScope / OpenAI / Anthropic / DeepSeek + 用户自定义，统一通过 litellm 调用。
- **安全分级**：每个 tool 有 `auto / confirm / double_confirm / blocked` 安全级别，`SafeGuard` 拦截执行。
- **配置驱动**：内置 Provider 在 `config.yaml`，自定义 Provider 在 `config/custom_providers.yaml`（运行时由 Web UI 写入）。

## 模块划分

### `voice_assistant.audio`

- `cloud_asr.py` — 云端 ASR（DashScope Paraformer），含 `HotwordsManager` 和回调累积纠正
- `funasr_asr.py` — 本地 ASR（可选）
- `asr_provider.py` — ASR 注册表，`create_asr_provider(config)` 按配置选择
- `tts.py` — `TTSProvider` Protocol + `EdgeTTSProvider`，提供 `synthesize` / `synthesize_to_bytes` / `synthesize_stream`

### `voice_assistant.agent`

- `llm_client.py` — `call_llm_with_tools` / `call_llm_with_tools_stream`（基于 litellm 统一多 Provider 接口）
- `orchestrator.py` — Agent 循环控制：`run` / `run_stream`，逐 token 流式 + tool 调度

### `voice_assistant.core`

- `session.py` — `VoiceSession`：ASR + Agent Loop + TTS + 历史的统一入口
- `model_manager.py` — 模型队列与故障切换（429/500 切换备用，400 不切）
- `asr_corrector.py` — 用 LLM 对 ASR 结果做语境纠错
- `dependencies.py` — 启动时依赖检查

### `voice_assistant.tools`

- `registry.py` — `@register_tool` 装饰器、`ToolResult`、参数校验、平台过滤
- `universal/` — 通用工具：文件 / 剪贴板 / 屏幕 / 输入 / 系统 / 实用 / 窗口 / 浏览器 / 媒体 / 网络 / 显示 / 通知 / 文件高级 / 快捷操作
- `platform_specific/mac_ops.py` `win_ops.py` — 平台原生操作
- `mcp/` — MCP (Model Context Protocol) 集成；`MCPManager` 在独立 asyncio 线程维持每 server 一个长驻 task，外部工具以 `mcp__<server>__<tool>` 注册到 `ToolRegistry`，支持 stdio / sse / streamable_http

### `voice_assistant.skills`

- `loader.py` — 扫描 `skills/**/SKILL.md`，解析 frontmatter (YAML) + body
- `selector.py` — `always` 全文 + `keywords` 命中 body 拼接 system prompt addendum
- `deps.py` — 检查 `required_mcp_servers / required_python / required_brew / required_env`
- `manager.py` — `SkillManager` 同步外观（reload / set_enabled / check）
- `meta_tools.py` — LLM 工具：`list_skills` / `check_skill_deps` / `enable_skill` / `disable_skill`

`VoiceSession.process_text*` 每次调 LLM 前先调 `skill_manager.build_addendum_for_message(user_text)`，通过 `extra_system` 透传到 `_build_messages` 拼到 `AGENT_SYSTEM_PROMPT` 末尾。

### `voice_assistant.security`

- `validation.py` — 输入边界校验、速率限制
- `safe_guard.py` — 工具调用分级拦截

### `voice_assistant.platform`

- `__init__.py` — `detect_platform()`（mac / windows）+ `MacAdapter / WindowsAdapter`

### `voice_assistant.config`

- `__init__.py` — `AppConfig` dataclass 树，`load_config()` 合并 `config.yaml` + `.env` + `config/custom_providers.yaml`
- `save_custom_provider()` / `update_custom_provider()` / `delete_custom_provider()` — Web UI Provider 持久化
- `_validate_config()` — 启动校验

### `voice_assistant.db`

SQLite 对话历史，表 `conversations` / `messages`。导出函数：`create_conversation` / `save_message` / `get_history` / `delete_conversation` / `delete_conversations` / `clear_history`。

## Web 层

### 后端 `web_ui.py`

主要 REST 端点：

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/config` | GET / POST | 通用配置 |
| `/api/providers` | GET | 列出所有 Provider 与模型 |
| `/api/providers/create` | POST | 创建自定义 Provider |
| `/api/providers/{id}` | PATCH / DELETE | 部分更新 / 删除自定义 Provider |
| `/api/providers/{id}/models` | GET | 从 Provider /models 端点拉取模型列表 |
| `/api/providers/switch` | POST | 切换活跃 Provider + 模型 |
| `/api/providers/api-key` | POST | 写入 API Key 到 .env |
| `/api/history` | GET | 对话历史列表 |
| `/api/history/{id}` | GET / DELETE | 单条对话详情 / 删除 |
| `/api/history/batch-delete` | POST | 批量删除 |
| `/api/history/clear` | POST | 清空 |
| `/ws/{client_id}` | WebSocket | 流式语音 / 文本通信 |

### 前端 `web_static/js/`

ES Module 拆分：

| 文件 | 职责 |
|------|------|
| `app.js` | 入口、事件绑定 |
| `state.js` | 全局状态 |
| `api.js` | REST 客户端 |
| `ws.js` | WebSocket 收发 |
| `audio.js` | 录音 + `StreamingAudioPlayer`（按 chunk 入队播放 TTS） |
| `ui.js` | 列表渲染、批量选择、消息流式显示 |
| `config.js` | 配置页面 + Provider 管理 |
| `utils.js` | 通用工具 |

## 数据流

### 文本输入（流式）

```
浏览器输入 → ws 发送 user_text
  → web_ui.py: VoiceSession.process_text_stream
  → AgentOrchestrator.run_stream
       ├─ 推 llm_token 事件（逐 token）
       ├─ 推 tool_start / tool_result（tool 调用）
       └─ 推 complete（最终回复）
  → web_ui.py 边收边推到前端
       ├─ ws 推 token → ui.js 增量渲染
       └─ ws 推 tts_chunk → audio.js StreamingAudioPlayer 逐句播放
```

### 语音输入

```
浏览器麦克风 → MediaRecorder（前端 VAD 静音检测）
  → ws 上传 audio_chunk
  → CloudASR.recognize_bytes
  → 与文本输入相同的下游
```

### 故障切换

LLM 调用失败时：
- `litellm.Timeout / APIConnectionError` → `ModelManager.switch_to_next_model()`
- `should_switch_model(error)` 判断 HTTP 429 / 5xx 切换；HTTP 400（输入问题）不切
- 主模型成功后 `reset_to_primary()`

## 配置树

```
AppConfig
├─ name, version
├─ asr: ASRConfig
│   ├─ model, base_url, api_key, language_hints, ...
│   ├─ hotwords: HotwordsConfig (enabled, vocabulary_id)
│   └─ local: LocalASRConfig (FunASR)
├─ llm: LLMConfig
├─ providers: ProvidersConfig (内置 + 自定义)
├─ audio: AudioConfig + TTSConfig
├─ vad: VADConfig
├─ history: HistoryConfig
├─ intent: IntentConfig
├─ logging: LoggingConfig
├─ agent: AgentConfig (max_iterations, confirmation_timeout)
└─ tools: ToolsConfig (blocked, overrides)
```

详见 [CONFIG.md](CONFIG.md) 和 [MODULES.md](MODULES.md)。
