# Voice Assistant 文档

纯 Web 的中文语音助手 — 浏览器录音 → ASR → Agent Loop → 流式 TTS。

## 文档导航

| 文档 | 内容 |
|------|------|
| [QUICKSTART.md](QUICKSTART.md) | 5 分钟跑起来 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构 |
| [MODULES.md](MODULES.md) | 各模块详解 |
| [CONFIG.md](CONFIG.md) | 配置参数 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 开发指南 |
| [API.md](API.md) | REST + WebSocket API |

## 核心能力

| 能力 | 说明 |
|------|------|
| Web UI | FastAPI + WebSocket + ES Module 前端 |
| 多 Provider | DashScope / OpenAI / Anthropic / DeepSeek + Web 端自定义 |
| 流式输出 | LLM token 级 + 分句 TTS |
| 云端 ASR | DashScope Paraformer-realtime-v2 |
| 本地 ASR | 可选 FunASR Paraformer-zh |
| TTS | Microsoft Edge-TTS |
| Agent Loop | LLM function calling + tool 执行 + 安全守卫 |
| 历史管理 | SQLite + 批量删除 |
| 故障转移 | 主模型 / 备用模型自动切换 |

## 数据流

```
浏览器录音 → WebSocket
    ↓
ASR 识别（云端 / 本地）
    ↓
意图识别 → Router
    ├─ 电脑操作 → Agent Loop（function calling + tool）
    └─ 对话 → 直接由 LLM 回答（流式）
    ↓
TTS 分块合成 → 浏览器 StreamingAudioPlayer 逐句播放
```
