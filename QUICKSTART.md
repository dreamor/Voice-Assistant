# 快速开始指南

## 5 分钟快速启动

### 步骤 1: 安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 2: 配置 API

1. 复制配置示例：
```bash
cp .env.sample .env
```

2. 编辑 `.env` 文件，填入你的 API 密钥：

```ini
ASR_API_KEY=你的语音识别API密钥
LLM_API_KEY=你的AI对话API密钥
```

### 步骤 3: 测试

```bash
pytest test_system.py -v
```

所有测试通过即可继续。

### 步骤 4: 运行

```bash
python voice_assistant_ai.py
```

## API 密钥获取

### 阿里云 DashScope (当前 ASR 和 LLM 共用)

1. 访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)
2. 开通语音服务和模型服务
3. 创建 API Key

两个配置使用相同的 API Key。

## 常见问题

### Q: 测试全部通过但程序无法运行？

检查 `.env` 文件是否正确创建，且 API 密钥是否有效。

### Q: 录音没有声音输入？

- 检查麦克风是否正常连接
- 检查系统麦克风权限

### Q: AI 回复为空？

- 检查阿里云 API 余额
- 检查网络连接

### Q: 语音识别失败？

- 确认使用 44100 Hz 采样率
- 检查阿里云 API 余额

## 下一步

- 调整 `.env` 中的 `VAD_THRESHOLD` 优化录音灵敏度
- 修改 `SYSTEM_PROMPT` 自定义 AI 行为
- 更换 `EDGE_TTS_VOICE` 使用其他音色