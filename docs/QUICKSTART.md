# Voice Assistant 快速开始

5 分钟跑起来。

## 1. 环境准备

```bash
# macOS: 安装 ffmpeg
brew install ffmpeg
```

## 2. 安装 uv 与依赖

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

> 需要 Python 3.10+。

## 3. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
DASHSCOPE_API_KEY=your-key
# 或者：OPENAI_API_KEY=sk-..., ANTHROPIC_API_KEY=..., DEEPSEEK_API_KEY=...
```

也可以**先启动**，再到 Web UI 配置页填入。

## 4. 启动

```bash
source .venv/bin/activate
python -m voice_assistant
```

控制台输出：

```
[Web] Starting Voice Assistant Web UI...
[Web] Visit: http://127.0.0.1:8000
```

浏览器打开 <http://127.0.0.1:8000>。

## 5. 使用

| 操作 | 说明 |
|------|------|
| 麦克风按钮 | 录音，VAD 自动检测说话结束 |
| 文本框 | 键盘输入 |
| 左侧 ⊕ | 新对话 |
| 左侧 ☑ | 进入批量选择模式（可全选 / 删除选中） |
| 左下 ⚙ | 配置页（Provider 切换、添加自定义 Provider、参数） |

## 6. 添加自定义 Provider

⚙ → 「添加 Provider」：

```
Provider ID:     deepseek-cn
名称:            DeepSeek 中国站
Base URL:        https://api.deepseek.com/v1
API Key:         sk-xxxx
LiteLLM Prefix:  openai
模型:            deepseek-chat（回车追加）
```

或填好 ID + Base URL + API Key 后点击「从 API 获取模型」自动拉取。

成功后会写入 `config/custom_providers.yaml`，并在列表中出现。

## 7. 本地 ASR（可选）

```bash
uv pip install -e ".[local-asr]"
```

```yaml
# config.yaml
asr:
  use_local: true
  local:
    enabled: true
    device: "cpu"  # 或 "cuda"
```

首次启动自动下载 Paraformer-zh 模型（约 2GB）到 `~/.cache/modelscope/hub/`。

## 8. 故障排查

| 现象 | 检查 |
|------|------|
| 浏览器麦克风无权限 | 需要 https 或 localhost 才能授权 |
| ASR 报错 401 / 403 | 确认 `DASHSCOPE_API_KEY` 已写入 `.env` 并重启 |
| LLM 报错 | 配置页确认 Provider API Key 已配置 |
| 音频播放无声 | 浏览器自动播放策略：先点击页面任意位置 |
| 启动前检查依赖 | `python -m voice_assistant --check` |

## 9. 进一步阅读

- [架构](ARCHITECTURE.md)
- [模块](MODULES.md)
- [配置](CONFIG.md)
- [开发](DEVELOPMENT.md)
