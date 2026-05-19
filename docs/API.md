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

#### 客户端 → 服务端

```json
{"type": "user_text", "text": "你好", "conversation_id": "..."}
{"type": "audio_chunk", "data": "<base64 wav/webm>", "format": "wav"}
{"type": "start_conversation", "title": "..."}
{"type": "tts_replay", "text": "..."}
{"type": "confirm_response", "confirm_id": "...", "approved": true}
```

#### 服务端 → 客户端

| `type` | 字段 | 触发时机 |
|--------|------|---------|
| `asr_result` | `text` | ASR 完成 |
| `llm_token` | `content` | LLM 逐 token |
| `tool_start` | `tool_name`, `arguments` | 工具调用开始 |
| `tool_result` | `tool_name`, `result`, `success` | 工具调用完成 |
| `tts_chunk` | `data`, `index` | TTS 分句合成 |
| `complete` | `response`, `intent_type` | 整轮完成 |
| `confirm_request` | `confirm_id`, `tool_name`, `arguments`, `level`, `message` | 需要二次确认 |
| `error` | `message` | 异常 |

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
from voice_assistant.tools.registry import ToolRegistry

orch = AgentOrchestrator(tool_registry=registry, max_iterations=5)
result = orch.run(user_text="...", conversation_history=[])
# result.response, result.tool_calls_made, result.iterations

for event in orch.run_stream("..."):
    # event.type: "llm_token" | "tool_start" | "tool_result" | "complete" | "error"
    pass
```

### `voice_assistant.agent.llm_client`

```python
from voice_assistant.agent.llm_client import call_llm_with_tools_stream

for event in call_llm_with_tools_stream(messages=[...], tools=[...]):
    # event.type: "token" | "tool_calls" | "finish"
    pass
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
)

init_db()
conv_id = create_conversation(title="新对话")
save_message(conv_id, role="user", content="你好")
msgs = get_conversation_history(conv_id, limit=10)
delete_conversations([conv1_id, conv2_id])
```
