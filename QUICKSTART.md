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

### 步骤 3: 运行测试

```bash
pytest test_system.py -v
```

所有测试通过即可继续。

### 步骤 4: 启动

```bash
python voice_assistant_ai.py
```

## API 密钥获取

### 阿里云 DashScope

当前 ASR 和 LLM 共用阿里云 DashScope：

1. 访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)
2. 开通语音识别服务和模型服务
3. 创建 API Key

两个配置使用相同的 API Key。

## 工作模式

### Interpreter 模式 (默认)

识别电脑操作指令，自动执行代码：

**支持的指令类型：**
- 文件操作：打开、创建、删除、移动、重命名
- 系统控制：打开应用、关闭窗口、启动、停止
- 截屏截图
- 搜索查找
- 下载上传
- 安装卸载

**示例：**
- "打开计算器" → 执行相应代码
- "截屏保存到桌面" → 执行截屏代码
- "在桌面创建 hello.txt" → 创建文件

### AI 模式

按 `I` 键切换到 AI 模式，进行纯对话：

- "今天天气怎么样"
- "给我讲个笑话"
- "帮我写一首诗"

## 交互控制

| 按键 | 功能 |
|------|------|
| Enter | 开始录音 |
| C | 清除对话历史 |
| H | 显示对话历史 |
| I | 切换 Interpreter/AI 模式 |
| Q | 退出程序 |

## 常见问题

### Q: 测试全部通过但程序无法运行？

检查 `.env` 文件是否正确创建，且 API 密钥是否有效。

### Q: 录音没有声音输入？

- 检查麦克风是否正常连接
- 检查系统麦克风权限
- 尝试调整 `VAD_THRESHOLD` 值

### Q: AI 回复为空？

- 检查阿里云 API 余额
- 检查网络连接

### Q: 语音识别失败？

- 确认使用 44100 Hz 采样率
- 检查阿里云 API 余额

### Q: Interpreter 模式不执行代码？

- 确认指令包含操作关键词
- 可以按 `I` 切换到 AI 模式查看 LLM 回复

## 下一步

- 调整 `.env` 中的 `VAD_THRESHOLD` 优化录音灵敏度
- 修改 `SYSTEM_PROMPT` 自定义 AI 行为
- 更换 `EDGE_TTS_VOICE` 使用其他音色
- 阅读 [完整文档](docs/README.md) 了解更多