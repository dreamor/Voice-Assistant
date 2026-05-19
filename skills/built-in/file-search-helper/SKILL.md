---
name: file-search-helper
description: 用户找文件/目录时优先使用 find_files + search_in_files 工具的工作流提示
trigger: keywords
keywords: ["找文件", "搜索文件", "查找内容", "find file", "search in"]
required_python: []
---

# 文件搜索工作流

当用户要找文件或在文件内容里搜关键词时：

1. **找文件名**：先用 `find_files(directory=..., pattern="*.ext")` 列候选
2. **查文件内容**：用 `search_in_files(pattern=..., directory=..., file_ext=...)`
3. 如果用户只给了关键词没给目录，默认从 `~/Documents` 开始；若仍无结果，向用户确认目录
4. 找到结果后**主动**：
   - 给出**完整路径**（不要省略）
   - 如果是文档/代码，列出**前 3 个匹配行的行号**
   - 询问是否要打开（`open_file`）或移动（`move_file`）

避免：
- 在用户没要求时打开/移动文件（要先确认）
- 单次搜索结果超过 50 行直接给 LLM —— 让工具自己截断
