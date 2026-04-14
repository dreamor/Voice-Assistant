# 快速开始指南

## 5 分钟快速启动

### 步骤 1: 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

> **系统要求**: Python 3.10 或更高版本

### 步骤 2: 安装依赖

```bash
# 使用启动脚本（推荐）
./start.sh

# 或手动安装
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev,local-llm]"
```

### 步骤 3: 配置 API

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

### 步骤 4: 运行测试

```bash
source .venv/bin/activate
pytest test_system.py -v
```

所有测试通过即可继续。

### 步骤 5: 启动

**方式 1: Web UI（推荐）**

```bash
# 启动 Web UI
python -m voice_assistant --web

# 或
python web_ui.py
```

然后在浏览器中打开：**http://127.0.0.1:8000**

**方式 2: 命令行模式**

```bash
# 使用启动脚本
./start.sh

# 或手动启动
source .venv/bin/activate
python run.py
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

### LLM 模式切换

按 `L` 键切换本地/在线 LLM：

| 模式 | 模型 | 说明 |
|------|------|------|
| 在线 | kimi-k2.5 | 需要网络，API 调用 |
| 本地 | gemma-4-E2B-it | 离线运行，需下载模型 |

## 本地模型设置

### 下载模型

从 HuggingFace 下载 Gemma-4-E2B-it LiteRT-LM 模型（约 2.4GB）：

```bash
# 使用 huggingface-cli
huggingface-cli download litert-community/gemma-4-E2B-it-litert-lm \
  --local-dir ./model_weights
```

或手动下载后放置到 `model_weights/gemma-4-E2B-it.litertlm`

### 启用本地模型

1. 安装本地模型依赖：
```bash
uv pip install -e ".[local-llm]"
```

2. 运行时按 `L` 键切换，或修改 `config.yaml`：
```yaml
llm:
  use_local: true
```

## 交互控制

### Web UI 操作

| 操作 | 说明 |
|------|------|
| 点击麦克风按钮 | 开始/停止录音 |
| 文本输入框 | 输入文字消息 |
| 设置面板 | 调整模型、温度、Token 等参数 |
| 清除历史按钮 | 清除对话历史 |

### 命令行模式按键

| 按键 | 功能 |
|------|------|
| Enter | 开始录音 |
| C | 清除对话历史 |
| H | 显示对话历史 |
| I | 切换 自动/AI 模式 |
| L | 切换 本地/在线 LLM |
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

### Q: 本地模型加载失败？

- 确认 Python 版本 >= 3.10
- 确认模型文件存在于 `model_weights/gemma-4-E2B-it.litertlm`
- 确认已安装 `litert-lm-api-nightly`

### Q: 电脑操作不执行？

- 确认指令包含操作关键词
- 检查 `config.yaml` 中 `interpreter.auto_run` 是否为 `true`

## 下一步

- 调整 `config.yaml` 中的 `vad.threshold` 优化录音灵敏度
- 更换 `audio.edge_tts_voice` 使用其他音色
- 下载本地模型实现完全离线运行
- 阅读 [完整文档](docs/README.md) 了解更多