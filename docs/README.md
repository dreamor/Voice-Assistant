# 语音助手项目文档

## 文档目录

- [架构文档](ARCHITECTURE.md) - 系统架构和技术方案
- [模块说明](MODULES.md) - 各模块功能详解
- [配置说明](CONFIG.md) - 配置参数详解
- [开发指南](DEVELOPMENT.md) - 开发指南和测试
- [API参考](API.md) - 接口文档

## 快速导航

### 核心模块

| 模块 | 功能 |
|------|------|
| `cloud_asr.py` | 阿里云 DashScope 语音识别 |
| `vad.py` | 语音活动检测 |
| `tts.py` | Edge-TTS 语音合成 |
| `ai_client.py` | LLM 对话（在线/本地） |
| `audio_player.py` | 音频播放 |
| `router.py` | 意图分类（LLM+关键词）和命令路由 |
| `chat.py` | 对话执行器 |
| `interpreter.py` | Open Interpreter 执行器 |

### 新功能

| 功能 | 说明 |
|------|------|
| LLM 意图识别 | 云端 LLM 语义理解 + 关键词兜底 |
| 模型自动切换 | 主模型故障时自动切换到备用模型 |
| VAD 语音检测 | 自动检测说话开始/结束，无需手动操作 |
| 中英文优化 | ASR 热词、参数优化、纠错 |

### 数据流

```
麦克风 → VAD录音 → 云端ASR识别 → 意图识别(LLM+关键词) → 执行器路由 → TTS合成 → 扬声器播放
                                            ↓
                                      本地/在线LLM
```

### LLM 模式

| 模式 | 模型 | 特点 |
|------|------|------|
| 在线 | kimi-k2.5 | 需网络，响应快 |

### 意图识别

| 策略 | 说明 |
|------|------|
| LLM 优先 | 云端 qwen-turbo 语义理解，返回意图类型 + 置信度 |
| 关键词兜底 | LLM 不可用或置信度 < 0.3 时回退到关键词匹配 |
| 意图类型 | `computer_control` / `query_answer` / `ordinary_chat` |