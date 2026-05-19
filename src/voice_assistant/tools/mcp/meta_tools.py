"""LLM 可调用的 MCP 反射工具

只读 + 开关类，安全级别 READ_ONLY。
不暴露写配置类工具（add/remove server）—— 那些走 Web UI。
"""
from voice_assistant.security.safe_guard import SecurityLevel
from voice_assistant.tools.registry import ToolDefinition


def _list_mcp_servers() -> str:
    """列出已注册的 MCP server 与其暴露的工具"""
    from voice_assistant.core.session import get_mcp_manager

    mgr = get_mcp_manager()
    if mgr is None:
        return "MCP 未启用或没有配置的 server"

    servers = mgr.list_servers()
    if not servers:
        return "暂无 MCP server"

    lines = []
    for s in servers:
        status = "✓" if s["ready"] else "✗"
        err = f" (error: {s['error']})" if s["error"] else ""
        tools_str = ", ".join(s["tools"]) if s["tools"] else "(无)"
        lines.append(
            f"{status} {s['id']} [{s['transport']}]{err}\n  tools: {tools_str}"
        )
    return "MCP servers:\n" + "\n".join(lines)


def get_mcp_meta_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="list_mcp_servers",
            description=(
                "列出当前已连接的 MCP server，包含每个 server 的连接状态和已注册的工具列表。"
                "用户问『有哪些 MCP server / 外部工具』时调用。"
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_list_mcp_servers,
            security_level=SecurityLevel.READ_ONLY,
            platforms=["mac", "windows"],
        ),
    ]
