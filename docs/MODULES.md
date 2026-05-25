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
│   │   ├── lifecycle.py         # AppLifecycle 单例（MCP/Skill/Registry 生命周期）
│   │   ├── model_manager.py     # Provider / 模型故障转移
│   │   ├── asr_corrector.py     # LLM 语境纠错
│   │   └── dependencies.py      # 依赖检查
│   ├── agent/
│   │   ├── orchestrator.py      # Agent Loop（run / run_stream）
│   │   ├── llm_client.py        # Function Calling 通信层（litellm + 重试 + 回退）
│   │   └── retry.py             # RetryPolicy / ErrorClass / 指数退避
│   ├── security/
│   │   ├── validation.py        # 输入边界 + 速率限制 + ToolRateLimiter
│   │   ├── safe_guard.py        # 工具分级拦截
│   │   └── ws_auth.py           # WebSocket HMAC 令牌认证
│   ├── tools/
│   │   ├── registry.py          # @register_tool + ToolResult + 参数校验 + 分组筛选
│   │   ├── tool_groups.py       # 工具分组定义（7 组）+ LLM 提示生成
│   │   ├── universal/           # 文件 / 剪贴板 / 屏幕 / 输入 / 系统 / 实用
│   │   └── platform_specific/   # mac_ops.py / win_ops.py
│   ├── web/                     # FastAPI Web 包（从 web_ui.py 拆分）
│   │   ├── app.py               # 应用工厂 + lifespan
│   │   ├── ws.py                # WebSocket 端点 + 流式 LLM/TTS
│   │   ├── routes.py            # 静态路由 + 配置校验
│   │   ├── config_api.py        # /api/config /api/models /api/ws-token
│   │   ├── providers_api.py     # /api/providers/* CRUD
│   │   ├── history_api.py       # /api/history/* CRUD
│   │   ├── mcp_skill_api.py     # /api/mcp/servers /api/skills/*
│   │   ├── audio.py             # 音频格式转换
│   │   └── middleware.py        # HTTP 中间件 + RateLimiter
│   └── platform/                # detect_platform + MacAdapter / WindowsAdapter
├── web_ui.py                    # 薄入口：from voice_assistant.web import create_app
├── web_static/                  # Web 前端 ES Module
├── config.yaml                  # 内置配置 + 内置 Provider
├── config/
│   ├── hotwords.json
│   ├── mcp_servers.yaml         # MCP 服务器配置
│   ├── secrets.example.yaml     # MCP secrets 模板
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
| `session.py` | `VoiceSession` 统一入口：`process_text()` / `process_text_stream()` / `recognize()` / `synthesize()` / `synthesize_stream()` / `get_history()`。每次 LLM 调用前注入 skill addendum + tool group hint |
| `lifecycle.py` | `AppLifecycle` 单例：管理 MCPManager / SkillManager / ToolRegistry 的生命周期，提供 `build_tool_registry()` / `build_skill_addendum()` / `shutdown()` |
| `model_manager.py` | Provider + 模型队列，HTTP 429/5xx 故障时自动切换备用模型 |
| `asr_corrector.py` | 用 LLM 对 ASR 结果做语境纠错（如「open interpreter」→「Open Interpreter」） |
| `dependencies.py` | 启动前依赖检查 |

## Agent 模块 (`agent/`)

| 文件 | 说明 |
|------|------|
| `orchestrator.py` | `run()` / `run_stream()`，生成 `AgentEvent`（llm_token / tool_start / tool_result / complete / error） |
| `llm_client.py` | `call_llm_with_tools()` / `call_llm_with_tools_stream()`，基于 litellm 统一 OpenAI / Anthropic / DashScope / DeepSeek 等，含重试循环与模型回退 |
| `retry.py` | `RetryPolicy` / `ErrorClass` / `classify_error` / `compute_delay` / `should_retry` — 指数退避重试基础设施 |

**关键设计**：Agent Loop 是唯一执行路径。LLM 自己决定是否调 tool；不调则直接生成回答（覆盖纯对话场景）。无独立 router / chat executor 分支。

## 工具系统 (`tools/`)

- `registry.py`: `@register_tool` 装饰器、`ToolResult` 数据类、参数校验、平台过滤、`get_openai_tools(groups)` 按分组筛选
- `tool_groups.py`: 工具分组定义（core / file_ops / system_ops / display_ops / media_ops / network_ops / input_ops），`get_group_summary()` 生成 LLM 提示
- `universal/`: 文件、剪贴板、屏幕、键鼠输入、系统、计算、窗口、浏览器、媒体、网络、显示、通知、文件高级、快捷操作，`run_python_code`（兜底任意 Python 任务，DANGEROUS 级别需二次确认）
- `platform_specific/`: 按系统加载 `mac_ops.py` / `win_ops.py`
- `mcp/`: 接入 Model Context Protocol，外部 server 暴露的工具会以 `mcp__<server>__<tool>` 命名注册到 ToolRegistry，支持 stdio/sse/streamable_http 三种 transport。配置 `config/mcp_servers.yaml`，secrets 走 `config/secrets.yaml`（gitignored）。

工具自动注册到 `ToolRegistry`，通过 `get_openai_tools()` 暴露给 LLM 做 function calling。

## Skill 系统 (`skills/`)

`SKILL.md` 风格的可复用知识/能力包。每次 LLM 调用前自动注入 system prompt：
- `trigger: always` 全文常驻
- `trigger: keywords` 命中关键词时注入 body
- `trigger: manual` 用户显式触发

`SkillManager` 加载 `skills/**/SKILL.md`，frontmatter 声明 `required_mcp_servers / required_python / required_brew / required_env`。
内置 LLM meta tools: `list_skills` / `check_skill_deps` / `enable_skill` / `disable_skill`。

## Web UI 配置 (`web/` + `web_static/`)

后端拆分为 10 个模块（`app.py` / `ws.py` / `routes.py` / `config_api.py` / `providers_api.py` / `history_api.py` / `mcp_skill_api.py` / `audio.py` / `middleware.py` / `__init__.py`），入口 `web_ui.py` 仅保留薄代理。

配置页（⚙️）除 Provider 外，新增：
- **MCP Servers**: 状态、暴露的工具列表（只读，编辑 yaml 后重启）
- **Skills**: 启停开关 / 重新扫描 / 依赖检查（运行时切换，不写回磁盘）

REST: `GET /api/mcp/servers`, `GET /api/skills`, `POST /api/skills/{name}/{enable|disable|reload}`

## 安全 (`security/`)

- `validation.py`: 输入边界校验 + 速率限制（`RateLimiter`）+ 每工具分组限流（`ToolRateLimiter`）
- `safe_guard.py`: 分级拦截（`auto` / `confirm` / `double_confirm` / `blocked`）
- `ws_auth.py`: WebSocket HMAC 令牌认证（本地开发跳过，非本地需 `/api/ws-token` 获取令牌）

每个 tool 定义 `safety_level`，Orchestrator 执行前先过 SafeGuard；`confirm` 级别会通过 WebSocket 推送 `confirm_request` 给前端，等待用户响应。

## 平台 (`platform/`)

- `detect_platform()`: 返回 `"mac"` / `"windows"`（其它系统会在创建 adapter 时抛 RuntimeError）
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
| `web/app.py` | FastAPI 应用工厂 + lifespan（启动时初始化 ToolRegistry/MCP/Skill，关闭时清理） |
| `web/ws.py` | WebSocket 端点 + `ConnectionManager` + 流式 LLM/TTS 推送（含确认回调、TTS 超时保护） |
| `web/routes.py` | 静态路由 + 配置校验 |
| `web/config_api.py` | `/api/config` `/api/models` `/api/ws-token` |
| `web/providers_api.py` | `/api/providers/*` CRUD |
| `web/history_api.py` | `/api/history/*` CRUD |
| `web/mcp_skill_api.py` | `/api/mcp/servers` `/api/skills/*` |
| `web/audio.py` | 音频格式转换（`convert_audio_to_wav`） |
| `web/middleware.py` | HTTP 中间件 + `RateLimiter` |
| `web_ui.py` | 薄入口：`from voice_assistant.web import create_app` |
| `web_static/js/app.js` | 入口 + 事件绑定 |
| `web_static/js/api.js` | REST 封装 |
| `web_static/js/ws.js` | WebSocket 消息收发 |
| `web_static/js/audio.js` | 录音 + `StreamingAudioPlayer`（逐句播放 TTS chunk） |
| `web_static/js/ui.js` | 列表渲染、批量选择、消息流式渲染 |
| `web_static/js/config.js` | 配置页 + Provider 管理（含 base_url 编辑、模型增删） |
| `web_static/js/state.js` | 全局状态 |

Web UI 与 `VoiceSession` 是唯一数据通路。
