"""MCP 工具 ↔ ToolRegistry 桥接

将 MCP server 暴露的工具包装为同步 handler 注册到 ToolRegistry。
handler 内部用 asyncio.run_coroutine_threadsafe 调度到 manager 的事件循环。
"""
import asyncio
import logging
from concurrent.futures import Future
from typing import Any

from voice_assistant.security.safe_guard import SecurityLevel
from voice_assistant.tools.registry import ToolDefinition

logger = logging.getLogger(__name__)


_LEVEL_MAP = {
    "read_only": SecurityLevel.READ_ONLY,
    "write": SecurityLevel.WRITE,
    "dangerous": SecurityLevel.DANGEROUS,
}


def make_tool_definition(
    *,
    server_id: str,
    mcp_tool_name: str,
    description: str,
    input_schema: dict,
    call_tool: Any,  # async callable: (name, args) -> result
    loop: asyncio.AbstractEventLoop,
    security_default: str = "write",
) -> ToolDefinition:
    """把 MCP 工具元数据包装成 ToolDefinition。

    - 工具名格式：`mcp__<server_id>__<tool_name>`，与 Claude Code 习惯一致
    - handler 同步阻塞，将异步调用提交到 manager 的事件循环
    """
    full_name = f"mcp__{server_id}__{mcp_tool_name}"

    def handler(**arguments) -> str:
        try:
            fut: Future = asyncio.run_coroutine_threadsafe(
                call_tool(mcp_tool_name, arguments), loop
            )
            # 30s 上限避免无限阻塞
            result = fut.result(timeout=30)
        except TimeoutError:
            return f"[MCP] {full_name} 调用超时（>30s）"
        except Exception as e:
            logger.exception(f"[MCP] {full_name} 调用失败")
            return f"[MCP] {full_name} 调用失败: {e}"

        return _stringify_mcp_result(result)

    return ToolDefinition(
        name=full_name,
        description=description or f"MCP tool from {server_id}",
        parameters=input_schema or {"type": "object", "properties": {}},
        handler=handler,
        security_level=_LEVEL_MAP.get(security_default, SecurityLevel.WRITE),
        platforms=["mac", "windows"],
    )


def _stringify_mcp_result(result: Any) -> str:
    """把 MCP CallToolResult 转成字符串供 LLM 消费"""
    # mcp.types.CallToolResult 有 content: list[TextContent | ImageContent | ...]
    if result is None:
        return ""
    content = getattr(result, "content", None)
    if content is None:
        return str(result)

    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(item))
    out = "\n".join(parts).strip()
    if getattr(result, "isError", False):
        return f"[MCP error] {out}"
    return out
