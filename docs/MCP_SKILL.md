# MCP & Skill 扩展

本文档说明如何为 Voice Assistant 接入外部 MCP server 和编写 Skill 包。

---

## 1. MCP（Model Context Protocol）

MCP 让 LLM 通过 function calling 调用外部服务（GitHub、文件系统、自定义业务接口）。
工具命名 `mcp__<server>__<tool>`，与原生 71 个工具同等可见。

### 1.1 添加 server

编辑 `config/mcp_servers.yaml`：

```yaml
servers:
  - id: filesystem
    transport: stdio
    enabled: true
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Documents"]
    security_default: read_only        # read_only | write | dangerous

  - id: github
    transport: stdio
    enabled: false
    command: ["npx", "-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: ${secrets.mcp.github.token}
    security_default: write

  - id: example_sse
    transport: sse
    url: https://api.example.com/mcp/sse
    headers:
      Authorization: Bearer ${secrets.mcp.example.token}

  - id: example_http
    transport: http
    url: https://api.example.com/mcp
    headers: { Authorization: Bearer ${secrets.mcp.example.token} }
```

### 1.2 Secrets

复制 `config/secrets.example.yaml` 为 `config/secrets.yaml`（已 gitignored），填入真实 token：

```yaml
mcp:
  github:
    token: ghp_xxx
```

在 `mcp_servers.yaml` 里用 `${secrets.path.to.key}` 引用。

### 1.3 Transport 速记

| Transport | 适合 | 关键字段 |
|---|---|---|
| `stdio` | 本地 npm/python server（最常见） | `command`, `env` |
| `sse` | 远程服务，单向流 | `url`, `headers` |
| `http` | 远程服务，Streamable HTTP | `url`, `headers` |

### 1.4 重启生效

启动时 `web_ui` lifespan 会扫描配置并建立连接。改动 yaml 后**重启服务**：

```bash
# kill 旧进程后
.venv/bin/python -m voice_assistant
```

### 1.5 验证

⚙️ 配置页 → MCP Servers 区块查看：
- ✓ 已连接 + 暴露工具列表
- ✗ 失败 + 错误原因

或 LLM 问"列出所有 MCP server"，触发 `list_mcp_servers` 工具。

### 1.6 安全级别

每个 server 默认 `security_default` 决定其工具的执行授权：
- `read_only`：自动执行
- `write`：单次确认（WebSocket 推送 `confirm_request`）
- `dangerous`：二次确认

可用 `config.yaml` 的 `tools.overrides` 对单个 `mcp__xxx__yyy` 工具单独 override。

---

## 2. Skill

Skill 是带 frontmatter 的 Markdown，描述某个工作流的最佳实践，LLM 调用时被注入到 system prompt。

### 2.1 目录约定

```
skills/
├── built-in/                   # 仓库自带（git 跟踪）
│   ├── echo-skill/SKILL.md
│   └── file-search-helper/SKILL.md
└── user/                       # 用户自建（建议 gitignore）
    └── my-skill/SKILL.md
```

只要文件名是 `SKILL.md`，目录嵌套不限。

### 2.2 SKILL.md 格式

```markdown
---
name: github-issue-triage
description: 三步式 issue 优先级分类
trigger: keywords              # keywords | always | manual
keywords: ["issue", "triage", "优先级"]
required_mcp_servers: [github]
required_python: ["requests>=2.31"]
required_brew: []
required_env: ["GITHUB_TOKEN"]
enabled: true                  # 可选，默认 true
---

# 详细指引

LLM 命中关键词后会读到这段内容。可以包含：
- 调用顺序约定
- 注意事项
- 输出格式要求
```

### 2.3 触发策略

| trigger | 何时注入到 LLM | 用途 |
|---|---|---|
| `always` | 每次调用都注入（system prompt 全文） | 项目角色设定、风格规范 |
| `keywords` | 用户消息命中 keyword 时注入 body | 任务工作流（最常用） |
| `manual` | 通过 `enable_skill` 工具显式启用 | 临时启停 |

### 2.4 依赖检查

加载时 SkillManager 检查每项 `required_*`：
- **MCP server**：查 `MCPManager.list_servers()`
- **Python 包**：`importlib.import_module`
- **brew 包**（仅 macOS）：`brew list --formula`
- **环境变量**：`os.environ`

缺失依赖**不阻塞**加载，但 `check_skill_deps` 会返回详情。
自动安装 pip 包默认**关闭**（避免 root 权限风险）；brew/npx 永不自动跑。

### 2.5 管理

- **Web UI**: ⚙️ 配置页 → Skills 区块（开关 + 重新扫描）
- **LLM**: `list_skills`, `check_skill_deps`, `enable_skill`, `disable_skill`

启停仅运行时，不写回磁盘；重启后回到 frontmatter 中声明的 `enabled` 状态。

---

## 3. 示例

### 3.1 内置 echo skill

```
skills/built-in/echo-skill/SKILL.md
```

用户说包含 "echo" 的话时注入：「优先调用 `mcp__echo__echo` 工具」。
这个 skill 依赖 echo MCP server（仓库自带自检 server）。

### 3.2 内置 file-search-helper

```
skills/built-in/file-search-helper/SKILL.md
```

引导 LLM 用 `find_files` + `search_in_files` 而不是猜路径。

### 3.3 一键测试

```bash
.venv/bin/python -m voice_assistant
# 浏览器打开 http://127.0.0.1:8000
# 输入 "echo hello"，观察 LLM 是否调用 mcp__echo__echo
```

---

## 4. 架构

```
ToolRegistry (71 内置 + N MCP + 5 meta)
    ▲                                 ▲
    │                                 │
MCPManager (后台 loop + 长驻 task)    SkillManager
    │                                 │
config/mcp_servers.yaml +             skills/**/SKILL.md
config/secrets.yaml                   (frontmatter + Markdown body)
```

LLM 调用前流程：
1. `VoiceSession.process_text*` 收用户消息
2. 调 `SkillManager.build_addendum_for_message(text)`
   → 拼接 always-skill 全文 + 命中 keyword-skill body
3. 通过 `extra_system` 参数透传到 `call_llm_with_tools*`
4. `_build_messages` 把 addendum 接到 `AGENT_SYSTEM_PROMPT` 末尾
5. LLM function calling，工具调用经过 `SafeGuard` 检查

更多细节见 `docs/MODULES.md`。
