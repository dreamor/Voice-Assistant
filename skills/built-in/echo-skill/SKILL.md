---
name: echo-skill
description: 自检用 skill，命中关键词「echo」时被注入
trigger: keywords
keywords: ["echo", "回声"]
required_mcp_servers: [echo]
---

# Echo Skill 用法

当用户提到 "echo" 时，优先调用 `mcp__echo__echo` 工具把消息原样返回。
