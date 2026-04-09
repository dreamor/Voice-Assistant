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
| `local_llm.py` | 本地 LLM 推理（LiteRT-LM） |
| `audio_player.py` | 音频播放 |

### 新功能

| 功能 | 说明 |
|------|------|
| 本地模型 | 使用 LiteRT-LM 运行 Gemma-4-E2B-it |
| LLM 切换 | 按 `L` 键切换本地/在线模式 |
| 中英文优化 | ASR 热词、参数优化、纠错 |

### 数据流

```
麦克风 → VAD录音 → 云端ASR识别 → 意图识别 → 执行器路由 → LLM处理 → TTS合成 → 扬声器播放
                                    ↓
                              本地/在线LLM
```

### LLM 模式

| 模式 | 模型 | 特点 |
|------|------|------|
| 在线 | kimi-k2.5 | 需网络，响应快 |
| 本地 | gemma-4-E2B-it | 离线运行，隐私保护 |