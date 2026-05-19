"""MCP (Model Context Protocol) 集成

把外部 MCP server 暴露的工具桥接到 ToolRegistry，
使 LLM 可以通过 function calling 调用它们。
"""
from voice_assistant.tools.mcp.config import (
    MCPServerConfig,
    load_secrets,
    load_servers,
)
from voice_assistant.tools.mcp.manager import MCPManager
from voice_assistant.tools.mcp.meta_tools import get_mcp_meta_tools

__all__ = [
    "MCPManager",
    "MCPServerConfig",
    "get_mcp_meta_tools",
    "load_servers",
    "load_secrets",
]
