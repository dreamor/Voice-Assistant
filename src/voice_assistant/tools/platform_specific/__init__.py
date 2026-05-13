"""
平台特定工具注册 - Layer 2
根据当前平台加载 mac_ops 或 win_ops
"""
from voice_assistant.tools.registry import ToolDefinition


def get_platform_tools(current_platform: str) -> list[ToolDefinition]:
    """返回当前平台的特定工具"""
    if current_platform == "mac":
        from voice_assistant.tools.platform_specific.mac_ops import get_mac_tools
        return get_mac_tools()
    elif current_platform == "windows":
        from voice_assistant.tools.platform_specific.win_ops import get_win_tools
        return get_win_tools()
    else:
        return []
