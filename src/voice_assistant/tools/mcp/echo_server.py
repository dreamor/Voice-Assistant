"""Vertical-slice 自检用的最小 MCP server (stdio)

提供一个 echo 工具，用于验证 MCP 接入端到端流程。
无需外部依赖，可直接通过 `python -m voice_assistant.tools.mcp.echo_server` 运行。
"""
import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server: Server = Server("voice-assistant-echo")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="echo",
            description="把输入文本原样返回，用于验证 MCP 接入。",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "任意文本"},
                },
                "required": ["message"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "echo":
        msg = arguments.get("message", "")
        return [TextContent(type="text", text=f"echo: {msg}")]
    return [TextContent(type="text", text=f"unknown tool: {name}")]


async def _run() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
