"""
工具分组与按需加载

将 71 个工具分为核心组（始终加载）和按需组（按需加载），
减少每次 LLM 调用发送的 tools schema 大小。
"""
import logging

logger = logging.getLogger(__name__)

# 工具分组定义
# core: 始终发送给 LLM 的工具（频繁使用、体积小）
# file_ops: 文件操作
# system_ops: 系统操作
# display_ops: 显示/窗口操作
# media_ops: 媒体控制
# network_ops: 网络操作
# input_ops: 输入模拟（鼠标/键盘）
TOOL_GROUPS: dict[str, list[str]] = {
    "core": [
        "calculate",
        "find_files",
        "get_system_info",
        "get_running_processes",
        "search_web",
        "open_url",
        "read_file",
        "write_file",
        "list_directory",
        "get_clipboard",
        "set_clipboard",
        "show_notification",
        "set_reminder",
        "run_python_code",
    ],
    "file_ops": [
        "open_file",
        "copy_file",
        "move_file",
        "delete_file",
        "delete_directory",
        "get_file_info",
        "search_in_files",
        "compress_files",
        "decompress_file",
        "empty_trash",
    ],
    "system_ops": [
        "launch_application",
        "quit_application",
        "is_application_running",
        "kill_process",
        "shutdown_computer",
        "restart_computer",
        "lock_screen",
        "sleep_display",
        "run_shortcut",
    ],
    "display_ops": [
        "take_screenshot",
        "take_screenshot_to_clipboard",
        "get_screen_size",
        "get_display_info",
        "get_brightness",
        "set_brightness",
        "set_wallpaper",
        "toggle_dark_mode",
        "get_active_window_title",
        "list_windows",
        "close_window",
        "minimize_window",
        "maximize_window",
        "resize_window",
        "move_window_to_center",
        "focus_window",
    ],
    "media_ops": [
        "media_play_pause",
        "media_next",
        "media_previous",
        "media_volume_up",
        "media_volume_down",
        "media_mute",
        "set_system_volume",
    ],
    "network_ops": [
        "get_network_info",
        "get_wifi_status",
        "toggle_wifi",
        "toggle_bluetooth",
        "ping_host",
    ],
    "input_ops": [
        "click_mouse",
        "double_click",
        "right_click",
        "move_mouse",
        "scroll",
        "type_text",
        "press_keys",
        "locate_on_screen",
        "open_spotlight",
    ],
}

# 分组描述（用于 system prompt 告知 LLM 可用工具组）
GROUP_DESCRIPTIONS: dict[str, str] = {
    "core": "核心工具（计算、搜索、系统信息、剪贴板、通知、代码执行）",
    "file_ops": "文件操作（打开、复制、移动、删除、搜索、压缩）",
    "system_ops": "系统操作（启动/退出应用、进程管理、关机/重启）",
    "display_ops": "显示与窗口（截图、亮度、壁纸、窗口管理）",
    "media_ops": "媒体控制（播放/暂停、音量、切歌）",
    "network_ops": "网络操作（网络信息、WiFi、蓝牙、Ping）",
    "input_ops": "输入模拟（鼠标点击、键盘输入、屏幕定位）",
}


def get_tool_group(tool_name: str) -> str:
    """获取工具所属分组。"""
    for group, tools in TOOL_GROUPS.items():
        if tool_name in tools:
            return group
    return "core"  # 未分组的工具归入 core


def get_tools_for_groups(groups: list[str] | None = None) -> list[str] | None:
    """获取指定分组包含的工具名列表。

    Args:
        groups: 分组名列表。None 表示返回所有工具（向后兼容）。

    Returns:
        工具名列表，或 None 表示所有工具。
    """
    if groups is None:
        return None

    result = []
    for group in groups:
        result.extend(TOOL_GROUPS.get(group, []))
    return result


def get_all_group_names() -> list[str]:
    """获取所有分组名。"""
    return list(TOOL_GROUPS.keys())


def get_group_summary() -> str:
    """生成分组摘要文本，用于 system prompt 告知 LLM 可用工具组。"""
    lines = ["可用工具分组（需要时可请求加载）："]
    for group, desc in GROUP_DESCRIPTIONS.items():
        tools = TOOL_GROUPS.get(group, [])
        lines.append(f"  - {group}: {desc} ({len(tools)} 个工具)")
    return "\n".join(lines)
