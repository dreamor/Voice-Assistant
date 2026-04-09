# 快速开始指南

## 5 分钟快速启动

### 步骤 1: 安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 2: 配置 API

1. 复制配置示例：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的 API 密钥：

```env
ASR_API_KEY=你的API密钥
LLM_API_KEY=你的API密钥
```

> **注意**：ASR 和 LLM 可使用相同的阿里云 DashScope API Key。

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

1. 访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)
2. 开通语音识别服务和模型服务
3. 创建 API Key

## 配置说明

项目使用**配置分离**架构：

| 文件 | 内容 |
|------|------|
| `.env` | API Key（敏感信息） |
| `config.yaml` | 其他配置（非敏感信息） |

详细配置说明请参考 [CONFIG.md](docs/CONFIG.md)。

## 工作模式

### 自动模式（默认）

自动识别用户意图，路由到对应执行器：

**电脑操作指令** → Open Interpreter 执行
- 文件操作：打开、创建、删除、移动
- 系统控制：打开应用、关闭窗口
- 截屏截图
- 搜索查找

**示例：**
- "打开计算器"
- "截屏保存到桌面"
- "在桌面创建 hello.txt"

**普通对话** → LLM 对话生成
- "今天天气怎么样"
- "给我讲个笑话"

### AI 对话模式

按 `I` 键切换，强制使用 LLM 对话：
- 适用于纯聊天场景
- 不执行电脑操作

## 交互控制

| 按键 | 功能 |
|------|------|
| Enter | 开始录音 |
| C | 清除对话历史 |
| H | 显示对话历史 |
| I | 切换 自动/AI 模式 |
| Q | 退出程序 |

## 常见问题

### Q: 测试全部通过但程序无法运行？

检查 `.env` 文件是否正确创建，且 API 密钥是否有效。

### Q: 录音没有声音输入？

- 检查麦克风是否正常连接
- 检查系统麦克风权限
- 调整 `config.yaml` 中的 `vad.threshold` 值

### Q: AI 回复为空？

- 检查阿里云 API 余额
- 检查网络连接

### Q: 语音识别失败？

- 确认使用 44100 Hz 采样率
- 检查阿里云 API 余额

### Q: 电脑操作不执行？

- 确认指令包含操作关键词
- 检查 `config.yaml` 中 `interpreter.auto_run` 是否为 `true`

## 下一步

- 调整 `config.yaml` 中的 `vad.threshold` 优化录音灵敏度
- 更换 `audio.edge_tts_voice` 使用其他音色
- 阅读 [完整文档](docs/README.md) 了解更多