# API 参考

Web UI 后端（FastAPI）+ Python 模块 API。

## REST API

所有响应均为 JSON。错误使用 HTTP 状态码 + `{"detail": "..."}`。

### 配置

#### `GET /api/config`

返回当前生效配置（已过滤敏感字段）。

```json
{
  "llm": {"provider": "dashscope", "model": "...", "base_url": "...", "max_tokens": 2000, "temperature": 0.7},
  "asr": {"use_local": false, "model": "..."},
  "audio": {"sample_rate": 16000, "tts_voice": "zh-CN-XiaoxiaoNeural"}
}
```

#### `POST /api/config`

部分更新配置：

```json
{
  "llm": {"temperature": 0.5, "max_tokens": 1500}
}
```

### Provider 管理

#### `GET /api/providers`

列出所有 Provider 与模型：

```json
{
  "providers": {
    "dashscope": {
      "name": "阿里云 DashScope",
      "has_key": true,
      "models": [{"id": "qwen-plus-latest", "name": "Qwen Plus"}],
      "is_custom": false,
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    }
  },
  "current_provider": "dashscope",
  "current_model": "qwen-plus-latest"
}
```

#### `POST /api/providers/create`

```json
{
  "id": "my-vllm",
  "name": "My vLLM",
  "base_url": "https://api.example.com/v1",
  "api_key": "sk-...",
  "litellm_prefix": "openai",
  "models": ["custom-7b"]
}
```

Provider ID 必须匹配 `^[a-zA-Z0-9_-]+$`，不可覆盖内置 ID。API Key 会写入 `.env`（变量名由 ID 推导，如 `MY_VLLM_API_KEY`）。

#### `PATCH /api/providers/{provider_id}`

部分更新自定义 Provider：

```json
{
  "name": "新名称",
  "base_url": "https://new-url.com/v1",
  "models": ["model-a", "model-b"],
  "litellm_prefix": "openai"
}
```

#### `DELETE /api/providers/{provider_id}`

删除自定义 Provider（不可删内置）。

#### `GET /api/providers/{provider_id}/models`

从 Provider 的 `/models` 端点拉取模型列表。需要 API Key 已配置。

```json
{"models": [{"id": "...", "name": "..."}], "total": 10}
```

#### `POST /api/providers/switch`

```json
{"provider_id": "dashscope", "model_id": "qwen-plus-latest"}
```

#### `POST /api/providers/api-key`

```json
{"provider_id": "openai", "api_key": "sk-..."}
```

### 对话历史

#### `GET /api/history?limit=20`

```json
{
  "conversations": [
    {"id": "...", "title": "今天天气", "created_at": "..."}
  ]
}
```

#### `GET /api/history/{conversation_id}`

```json
{
  "id": "...",
  "title": "...",
  "created_at": "...",
  "messages": [
    {"role": "user", "content": "...", "created_at": "..."},
    {"role": "assistant", "content": "...", "created_at": "..."}
  ]
}
```

#### `DELETE /api/history/{conversation_id}`

```json
{"success": true}
```

#### `POST /api/history/batch-delete`

```json
{"ids": ["conv1", "conv2"]}
```

返回 `{"deleted": 2}`。

#### `POST /api/history/clear`

清空所有对话。返回 `{"success": true}`。

#### `GET /api/history/{conversation_id}/tree`

获取对话的树结构消息（包含 node_id 和 parent_id）。

```json
{
  "conversation_id": "...",
  "nodes": [
    {"id": 1, "role": "user", "content": "...", "created_at": "...", "node_id": "uuid-1", "parent_id": null, "metadata": {}},
    {"id": 2, "role": "assistant", "content": "...", "created_at": "...", "node_id": "uuid-2", "parent_id": "uuid-1", "metadata": {}}
  ]
}
```

#### `POST /api/history/{conversation_id}/branch`

从指定消息节点创建分支。

```json
{"parent_node_id": "uuid-1", "role": "user", "content": "换一种回答"}
```

返回：

```json
{"success": true, "node_id": "uuid-3", "parent_node_id": "uuid-1"}
```

#### `PUT /api/history/{conversation_id}/active`

切换活跃分支到指定叶子节点。

```json
{"leaf_node_id": "uuid-2"}
```

返回：

```json
{"success": true, "active_leaf_id": "uuid-2"}
```

### 认证

#### `GET /api/ws-token`

获取 WebSocket 认证令牌（HMAC 签名，5 分钟有效）。

```json
{"token": "1716633600.abc123def456...", "client_id": "recommended-uuid"}
```

本地访问（localhost/127.0.0.1）默认不需要令牌。

### MCP / Skill

详细使用见 [MCP_SKILL](MCP_SKILL.md)。

#### `GET /api/mcp/servers`

列出当前所有 MCP server 的运行态。

```json
{
  "servers": [
    {
      "id": "echo",
      "transport": "stdio",
      "enabled": true,
      "ready": true,
      "error": null,
      "tools": ["mcp__echo__echo"]
    }
  ]
}
```

- `ready=false` 时 `error` 会包含失败原因。
- 编辑 `config/mcp_servers.yaml` 后需重启服务，本端点不写回磁盘。

#### `GET /api/skills`

列出所有 skill + 启停状态 + 依赖检查摘要。

```json
{
  "skills": [
    {
      "name": "echo-skill",
      "description": "...",
      "trigger": "keywords",
      "keywords": ["echo"],
      "enabled": true,
      "deps": {
        "mcp_servers": ["echo"],
        "python": [],
        "brew": [],
        "env": []
      },
      "deps_ok": true,
      "deps_missing": null
    }
  ]
}
```

`deps_missing` 在 `deps_ok=false` 时携带每类缺失项。

#### `POST /api/skills/{name}/enable` · `POST /api/skills/{name}/disable`

运行时切换 skill 启停（不写回磁盘）。

- `200 OK` `{"success": true, "name": "...", "enabled": true|false}`
- `404` `{"detail": "未找到 skill: <name>"}`
- `503` `{"detail": "Skill 系统未启用"}`

#### `POST /api/skills/reload`

重新扫描 `skills/` 目录。返回 `{"success": true, "count": N}`。

## WebSocket

### `ws://127.0.0.1:8000/ws/{client_id}`

`client_id` 由前端生成（建议 UUID）。

**认证**：非本地访问需在连接时附加 `?token=<HMAC_TOKEN>`，令牌通过 `GET /api/ws-token` 获取。本地访问（localhost/127.0.0.1）默认跳过认证。

#### 客户端 → 服务端

```json
{"type": "start_conversation", "title": "新对话"}
{"type": "load_conversation", "conversation_id": "..."}
{"type": "text_message", "content": "你好"}
{"type": "audio_data", "base64Audio": "<base64>", "format": "audio/wav"}
{"type": "start_audio_stream"}
{"type": "audio_chunk", "data": "<base64 int16 PCM>"}
{"type": "stop_audio_stream"}
{"type": "ping"}
{"type": "confirm_response", "confirm_id": "...", "approved": true}
{"type": "replay_tts", "content": "..."}
```

> **流式语音路径**（推荐）：`start_audio_stream` → 多次 `audio_chunk` → 服务端收到 `is_sentence_end` 后推 `vad_end`（含识别文本），前端停录并直发 `text_message`。
> **批量语音路径**（旧）：录完后一次性发 `audio_data`（WebM/WAV），服务端 ASR 后推 `asr_result`。

#### 服务端 → 客户端

| `type` | 字段 | 触发时机 |
|--------|------|---------|
| `conversation_started` | `conversation_id` | 新对话创建 |
| `conversation_loaded` | `conversation_id` | 加载已有对话 |
| `vad_end` | `text` | 实时 ASR 检测到语义完整，携带识别文本（流式路径） |
| `asr_processing` | — | ASR 处理中（批量路径） |
| `asr_result` | `content` | ASR 完成（批量路径） |
| `agent_start` | — | Agent 循环开始 |
| `turn_start` | `iteration` | 一轮 LLM 调用开始 |
| `message_delta` | `content` | LLM 逐 token（替代旧 `llm_stream`） |
| `turn_end` | `iteration` | 一轮 LLM 调用结束 |
| `tool_call` | `tool_name`, `tool_arguments`, `tool_call_id` | LLM 决定调用工具 |
| `executing` | `tool_name`, `tool_call_id` | 工具执行开始（替代旧 `tool_start`） |
| `execution_complete` | `tool_name`, `tool_call_id`, `success`, `data`, `display_hint`, `duration_ms` | 工具执行完成 |
| `agent_end` | `response`, `tool_calls` | Agent 循环结束（替代旧 `complete`） |
| `llm_thinking` | — | LLM 开始思考 |
| `llm_stream` | `content` | LLM 逐 token（向后兼容） |
| `llm_complete` | `content` | LLM 回复完成 |
| `tts_generating` | — | TTS 生成中 |
| `tts_audio` | `data`, `format` | TTS 音频（非流式） |
| `tts_chunk` | `data`, `format`, `chunk_index` | TTS 分句流式 |
| `tts_complete` | — | TTS 流式完成 |
| `confirm_required` | `confirm_id`, `tool_name`, `arguments`, `message`, `level` | 需要二次确认 |
| `compact` | — | 上下文压缩通知（预留） |
| `pong` | — | 心跳响应 |
| `error` | `message` | 异常 |

**display_hint 类型**：工具结果声明展示意图，前端按 hint 选择渲染组件：

| hint | 说明 | data 字段 |
|------|------|-----------|
| `text` | 纯文本（默认） | — |
| `code` | 代码块 | `language` |
| `table` | 表格 | `headers`, `rows` |
| `image` | 图片 | `url` |
| `markdown` | Markdown 渲染 | — |
| `link` | 链接 | `url` |
| `file` | 文件卡片 | `filename`, `size` 等 |
| `error` | 错误展示 | — |

## Python 模块 API

### `voice_assistant.core.session.VoiceSession`

统一会话入口：

```python
from voice_assistant.core.session import VoiceSession

session = VoiceSession(max_response_length=200)
session.initialize()

# 同步处理
result = session.process_text("打开 VS Code")
print(result.response)  # str
print(result.execution_output)  # tool 调用列表

# 流式处理
for event in session.process_text_stream("讲个笑话"):
    if event.type == "llm_token":
        print(event.content, end="", flush=True)
    elif event.type == "complete":
        print(event.result.response)

# ASR
text = session.recognize(wav_bytes, sample_rate=16000)

# TTS
mp3 = session.synthesize("你好")
for chunk in session.synthesize_stream("你好世界"):
    play(chunk)

# 历史
session.set_history(history_list)
session.get_history()
session.clear_history()

session.cleanup()
```

### `voice_assistant.agent.orchestrator.AgentOrchestrator`

```python
from voice_assistant.agent.orchestrator import AgentOrchestrator
from voice_assistant.agent.events import EventType
from voice_assistant.tools.registry import ToolRegistry

orch = AgentOrchestrator(tool_registry=registry, max_iterations=5)
result = orch.run(user_text="...", conversation_history=[])
# result.response, result.tool_calls_made, result.iterations

for event in orch.run_stream("..."):
    # event.type: EventType.AGENT_START | EventType.MESSAGE_DELTA | EventType.TOOL_CALL
    #            | EventType.TOOL_EXECUTION_START | EventType.TOOL_EXECUTION_END
    #            | EventType.TURN_START | EventType.TURN_END
    #            | EventType.AGENT_END | EventType.ERROR
    pass
```

### `voice_assistant.agent.events`

```python
from voice_assistant.agent.events import EventType, AgentEvent, AgentResult, new_call_id

# 结构化事件类型
EventType.AGENT_START        # Agent 循环开始
EventType.AGENT_END          # Agent 循环结束
EventType.TURN_START         # 一轮 LLM 调用开始
EventType.TURN_END           # 一轮 LLM 调用结束
EventType.MESSAGE_DELTA      # LLM 文本增量
EventType.TOOL_CALL          # LLM 决定调用工具（含参数）
EventType.TOOL_EXECUTION_START  # 工具执行开始
EventType.TOOL_EXECUTION_END    # 工具执行结束（含结果、耗时）
EventType.CONFIRM_REQUIRED  # 需要用户确认
EventType.ERROR              # 错误

# AgentEvent 包含: type, content, tool_name, tool_arguments, tool_call_id,
#                  tool_result, tool_result_data, tool_display_hint, tool_success,
#                  duration_ms, iteration, result
# AgentResult 包含: success, response, tool_calls_made, iterations, confirmations_needed
```

### `voice_assistant.agent.hooks`

```python
from voice_assistant.agent.hooks import HookChain, HookContext, HookResult
from voice_assistant.agent.hooks import SafeGuardHook, RateLimitHook, ValidationHook
from voice_assistant.agent.hooks import AuditLogHook, MetricsHook

# 工具执行中间件管道 — before/after hook 链
chain = HookChain()
chain.add(RateLimitHook())       # 速率限制
chain.add(ValidationHook())      # 参数校验
chain.add(SafeGuardHook(guard))  # 安全检查

before_result = chain.run_before(ctx)  # ctx: HookContext(tool_name, arguments, ...)
if not before_result.proceed:
    # 操作被阻止
    pass

chain.run_after(ctx)  # ctx.result 可被 after hook 修改

# 内置 hook:
# SafeGuardHook  — 安全分级拦截（替代 ToolRegistry 内联检查）
# RateLimitHook  — 速率限制
# ValidationHook — 参数校验
# AuditLogHook   — 审计日志（after hook）
# MetricsHook    — 执行指标（after hook，get_stats() 返回统计）
```

### `voice_assistant.core.events`

```python
from voice_assistant.core.events import EventBus, Event, EventName, get_event_bus

# 全局事件总线 — 通知/订阅，不可拦截（与 Hook 互补）
bus = get_event_bus()  # 全局单例

bus.on(EventName.TOOL_AFTER, lambda e: print(e.data))
bus.emit(Event(name=EventName.AGENT_START, data={"user_text": "..."}))

# 事件类型:
# AGENT_START / AGENT_END / TOOL_BEFORE / TOOL_AFTER
# MESSAGE_CREATED / COMPACT_START / COMPACT_END / ERROR
```

### `voice_assistant.core.compaction`

```python
from voice_assistant.core.compaction import compact, should_compact, estimate_tokens

# 上下文压缩 — 当 token 逼近上限时，用 LLM 对旧消息生成摘要
messages = [{"role": "user", "content": "..."}, ...]

if should_compact(messages, max_context_tokens=6000):
    result = compact(messages, max_context_tokens=6000)
    # result.summary: LLM 生成的摘要
    # result.messages_removed: 被移除的消息数
    # result.messages_kept: 保留的消息数
    # result.tokens_before / tokens_after: token 估算
```

### `voice_assistant.core.session_tree`

```python
from voice_assistant.core.session_tree import SessionTree, TreeNode

# 树形会话结构 — 支持分支、切换、摘要
tree = SessionTree()
n1 = tree.append("user", "你好")
n2 = tree.append("assistant", "你好！")

# 从 n1 创建分支
n3 = tree.branch(n1, role="assistant", content="嗨！")

# 切换活跃分支
tree.switch_branch(n2)

# 获取活跃分支消息列表
messages = tree.to_messages()

# 列出分支
branches = tree.list_branches(n1)

# 序列化/反序列化
data = tree.to_dict()
restored = SessionTree.from_dict(data)

# 从扁平消息列表构建（兼容旧数据）
tree.from_messages([{"role": "user", "content": "hello"}])
```

### `voice_assistant.agent.llm_client`

```python
from voice_assistant.agent.llm_client import call_llm_with_tools, call_llm_with_tools_stream

# 同步调用（含自动重试 + 模型回退）
result = call_llm_with_tools(user_text="你好", tools=[...], conversation_history=[], extra_system="")
# result: {"finish_reason": "stop"|"tool_calls"|"error", "content": str|None, "tool_calls": list|None}

# 流式调用（含自动重试 + 模型回退）
for event in call_llm_with_tools_stream(user_text="你好", tools=[...], extra_system=""):
    # event.type: "token" | "tool_calls" | "error" | "done"
    pass
```

### `voice_assistant.agent.retry`

```python
from voice_assistant.agent.retry import RetryPolicy, ErrorClass, classify_error, should_retry, compute_delay

policy = RetryPolicy(max_retries=3, base_delay=1.0, backoff_factor=2.0, jitter=0.1, max_delay=30.0)
error_class = classify_error(exception)  # TIMEOUT / CONNECTION / RATE_LIMIT / SERVER_ERROR / CLIENT_ERROR / UNKNOWN
should_retry(error_class)  # True for retryable errors
delay = compute_delay(attempt, policy, error_class, retry_after=5.0)  # seconds
```

### `voice_assistant.core.lifecycle`

```python
from voice_assistant.core.lifecycle import get_lifecycle, shutdown_lifecycle

lc = get_lifecycle()
registry = lc.build_tool_registry()       # 构建 ToolRegistry + 启动 MCP/Skill
addendum = lc.build_skill_addendum(text)   # 生成 Skill 提示补丁
lc.shutdown()                              # 关闭 MCP/Skill/Registry
```

### `voice_assistant.tools.tool_groups`

```python
from voice_assistant.tools.tool_groups import get_tool_group, get_tools_for_groups, get_group_summary

group = get_tool_group("open_file")           # "file_ops"
tools = get_tools_for_groups(["core"])         # 核心工具名集合
hint = get_group_summary()                    # LLM 提示文本
```

### `voice_assistant.tools.registry`

```python
from voice_assistant.tools.registry import register_tool, ToolResult

@register_tool(
    name="my_tool",
    description="...",
    parameters={"type": "object", "properties": {...}, "required": [...]},
    safety_level="confirm",  # auto / confirm / double_confirm / blocked
)
def my_tool(arg1: str) -> ToolResult:
    return ToolResult(success=True, data={"result": ...})
```

### `voice_assistant.audio.cloud_asr.CloudASR`

```python
from voice_assistant.audio.cloud_asr import CloudASR

asr = CloudASR()
text = asr.recognize_bytes(wav_bytes, sample_rate=16000)
text = asr.recognize_from_file("audio.wav")
```

### `voice_assistant.audio.cloud_asr.RealtimeASRSession`

流式识别会话，边录边识别，语义完整时回调。

```python
from voice_assistant.audio.cloud_asr import RealtimeASRSession

session = RealtimeASRSession(
    on_sentence_end=lambda text: print("识别完成:", text),
    on_error=lambda msg: print("错误:", msg),
)
session.start()
session.send_chunk(pcm_int16_bytes)  # 可多次调用，每次 100~200ms PCM
session.stop()
```

### `voice_assistant.audio.tts`

```python
from voice_assistant.audio.tts import create_tts_provider, EdgeTTSProvider

tts = create_tts_provider(config)
mp3 = tts.synthesize_to_bytes("你好")
for chunk in tts.synthesize_stream("你好世界，今天天气真好"):
    play(chunk)
```

### `voice_assistant.core.model_manager`

```python
from voice_assistant.core.model_manager import model_manager

queue = model_manager.build_model_queue()
current = model_manager.get_current_model()  # ModelConfig
model_manager.switch_to_next_model()        # 故障切换
model_manager.reset_to_primary()
model_manager.switch_provider("openai", "gpt-4o")
```

### `voice_assistant.config`

```python
from voice_assistant.config import (
    config,                       # 全局 AppConfig
    save_custom_provider,
    update_custom_provider,
    delete_custom_provider,
)

config.llm.model        # 当前模型
config.providers.providers  # dict[str, ProviderConfig]
config.asr.hotwords.vocabulary_id

save_custom_provider(
    provider_id="my-llm",
    name="My LLM",
    base_url="https://api.example.com/v1",
    api_key_env="MY_LLM_API_KEY",
    litellm_prefix="openai",
    models=["model-a"],
)
```

### `voice_assistant.db`

```python
from voice_assistant.db import (
    init_db,
    create_conversation, save_message,
    get_conversation_history, get_history,
    delete_conversation, delete_conversations, clear_history,
    save_message_with_tree, get_conversation_tree,
)

init_db()
conv_id = create_conversation(title="新对话")
save_message(conv_id, role="user", content="你好")
msgs = get_conversation_history(conv_id, limit=10)
delete_conversations([conv1_id, conv2_id])

# 树结构支持（node_id / parent_id / metadata）
node_id = save_message_with_tree(conv_id, role="user", content="你好",
                                  node_id="uuid-1", parent_id=None)
tree_msgs = get_conversation_tree(conv_id)  # 返回含 node_id/parent_id 的消息列表
```
