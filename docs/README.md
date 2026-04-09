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
| `cloud_asr.py` | 阿里云DashScope语音识别 |
| `vad.py` | 语音活动检测 |
| `tts.py` | Edge-TTS语音合成 |
| `ai_client.py` | OpenRouter AI对话 |
| `audio_player.py` | 音频播放 |

### 数据流

```
麦克风 → VAD录音 → 云端ASR识别 → AI处理 → TTS合成 → 扬声器播放
```