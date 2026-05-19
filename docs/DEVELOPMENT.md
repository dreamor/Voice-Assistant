# 开发指南

## 环境

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
# 可选：本地 ASR
uv pip install -e ".[local-asr]"
```

## 本地启动

```bash
source .venv/bin/activate
python -m voice_assistant
# 浏览器: http://127.0.0.1:8000
```

依赖检查：

```bash
python -m voice_assistant --check
```

## 项目结构

```
voice-assistant/
├── web_ui.py                       # FastAPI 应用 + WebSocket
├── web_static/
│   ├── index.html
│   ├── style.css
│   └── js/
│       ├── app.js                  # 入口、事件绑定
│       ├── state.js                # 全局状态
│       ├── api.js                  # REST 客户端
│       ├── ws.js                   # WebSocket
│       ├── audio.js                # 录音 + StreamingAudioPlayer
│       ├── ui.js                   # 列表、消息、批量选择
│       ├── config.js               # 配置页（Provider 管理）
│       └── utils.js
├── src/voice_assistant/
│   ├── __main__.py                 # 入口
│   ├── db.py                       # SQLite
│   ├── config/                     # 配置加载、custom_providers.yaml 读写
│   ├── audio/                      # cloud_asr / funasr_asr / tts
│   ├── core/                       # session / model_manager / asr_corrector
│   ├── agent/                      # orchestrator / llm_client (Agent Loop)
│   ├── tools/                      # registry + universal + platform_specific
│   ├── security/                   # validation + safe_guard
│   └── platform/                   # 平台检测
├── tests/
└── docs/
```

## 测试

```bash
pytest tests/ -v
pytest tests/test_audio/test_cloud_asr_callback.py -v   # 单文件
pytest --cov=voice_assistant tests/                     # 覆盖率
```

新增功能必须配套测试，目标覆盖率 ≥ 80%。

## 代码风格

```bash
ruff check src/ tests/
ruff format src/ tests/
pyright src/
```

## 添加新工具（Tool）

`src/voice_assistant/tools/` 下新建模块，`@register_tool` 注册：

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

会自动出现在 LLM 的 function calling 工具列表中。

> 如果工具来自外部服务（GitHub / 文件系统 / 自建 server），优先考虑接入 MCP server 而不是写新 Python tool，详见 [MCP_SKILL](MCP_SKILL.md)。

## 添加 Skill（提示包）

在 `skills/` 下放一个目录加 `SKILL.md`，frontmatter 声明触发方式与依赖。LLM 调用前会自动注入。详见 [MCP_SKILL §2](MCP_SKILL.md#2-skill)。

## 添加新 Provider

**首选**：Web UI 配置页 → 「添加 Provider」即可，无需写代码。

代码层新增内置 Provider：在 `config.yaml` 的 `providers:` 节点添加。

## 调试

启用 DEBUG 日志：

```yaml
# config.yaml
logging:
  level: "DEBUG"
  file: "logs/voice.log"
```

WebSocket 帧调试：浏览器 DevTools → Network → WS → 选中连接 → Messages 标签。

## 常用命令

| 命令 | 说明 |
|------|------|
| `python -m voice_assistant` | 启动 Web UI |
| `python -m voice_assistant --check` | 依赖检查 |
| `pytest tests/ -v` | 运行测试 |
| `ruff check .` | Lint |
| `ruff format .` | 格式化 |
| `pyright src/` | 类型检查 |

## 测试 ASR / TTS / VAD

ASR：

```python
from voice_assistant.audio.cloud_asr import CloudASR
asr = CloudASR()
text = asr.recognize_bytes(open("sample.wav", "rb").read())
print(text)
```

TTS：

```python
from voice_assistant.audio.tts import create_tts_provider
tts = create_tts_provider()
data = await tts.synthesize("你好")
open("out.mp3", "wb").write(data)
```

## 贡献

1. fork → 新分支
2. 写测试 → 写实现 → 跑测试
3. `ruff check && pyright` 通过
4. 提交 PR
