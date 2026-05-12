"""
通用工具注册 - Layer 1
跨平台纯 Python 工具（文件、系统、输入、屏幕、剪贴板、计算器）
"""
from voice_assistant.tools.registry import ToolDefinition
from voice_assistant.security.safe_guard import SecurityLevel

from voice_assistant.tools.universal.file_ops import (
    read_file, write_file, delete_file, list_directory, find_files, delete_directory,
)
from voice_assistant.tools.universal.system_ops import (
    get_system_info, get_running_processes, get_active_window_title, kill_process,
)
from voice_assistant.tools.universal.input_ops import (
    move_mouse, click_mouse, double_click, right_click, type_text, press_keys, scroll,
)
from voice_assistant.tools.universal.screen_ops import (
    take_screenshot, locate_on_screen, get_screen_size,
)
from voice_assistant.tools.universal.clipboard_ops import (
    get_clipboard, set_clipboard,
)
from voice_assistant.tools.universal.utility_ops import (
    calculate,
)


def get_universal_tools() -> list[ToolDefinition]:
    """返回所有通用层工具定义"""
    return [
        # 文件操作
        ToolDefinition(
            name="read_file",
            description="读取文件内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "max_lines": {"type": "integer", "description": "最大行数", "default": 200},
                },
                "required": ["path"],
            },
            handler=read_file,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="write_file",
            description="写入文件内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "写入内容"},
                },
                "required": ["path", "content"],
            },
            handler=write_file,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="delete_file",
            description="删除文件（不可恢复）",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                },
                "required": ["path"],
            },
            handler=delete_file,
            security_level=SecurityLevel.DANGEROUS,
        ),
        ToolDefinition(
            name="list_directory",
            description="列出目录内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径", "default": "."},
                },
                "required": [],
            },
            handler=list_directory,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="find_files",
            description="搜索文件（按名称模式匹配）",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "搜索模式"},
                    "directory": {"type": "string", "description": "搜索目录", "default": "."},
                },
                "required": ["pattern"],
            },
            handler=find_files,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="delete_directory",
            description="删除整个目录（不可恢复）",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径"},
                },
                "required": ["path"],
            },
            handler=delete_directory,
            security_level=SecurityLevel.DANGEROUS,
        ),
        # 系统信息
        ToolDefinition(
            name="get_system_info",
            description="获取系统信息（OS、CPU、内存、磁盘等）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_system_info,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="get_running_processes",
            description="获取正在运行的进程列表",
            parameters={
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "返回数量", "default": 20},
                },
                "required": [],
            },
            handler=get_running_processes,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="get_active_window_title",
            description="获取当前活跃窗口标题",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_active_window_title,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="kill_process",
            description="终止进程",
            parameters={
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "进程 ID"},
                },
                "required": ["pid"],
            },
            handler=kill_process,
            security_level=SecurityLevel.DANGEROUS,
        ),
        # 输入控制
        ToolDefinition(
            name="move_mouse",
            description="移动鼠标到指定坐标",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X 坐标"},
                    "y": {"type": "integer", "description": "Y 坐标"},
                },
                "required": ["x", "y"],
            },
            handler=move_mouse,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="click_mouse",
            description="点击鼠标",
            parameters={
                "type": "object",
                "properties": {
                    "button": {"type": "string", "description": "按钮: left/right/middle", "default": "left"},
                },
                "required": [],
            },
            handler=click_mouse,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="double_click",
            description="双击鼠标",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=double_click,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="right_click",
            description="右键点击",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=right_click,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="type_text",
            description="键盘输入文本",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "输入文本"},
                },
                "required": ["text"],
            },
            handler=type_text,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="press_keys",
            description="按下组合键，如 command+c",
            parameters={
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "按键列表，如 ['command', 'c']",
                    },
                },
                "required": ["keys"],
            },
            handler=lambda keys: press_keys(*keys),
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="scroll",
            description="滚动鼠标滚轮",
            parameters={
                "type": "object",
                "properties": {
                    "amount": {"type": "integer", "description": "滚动量，正向上负向下", "default": -3},
                },
                "required": [],
            },
            handler=scroll,
            security_level=SecurityLevel.WRITE,
        ),
        # 屏幕操作
        ToolDefinition(
            name="take_screenshot",
            description="截取屏幕截图",
            parameters={
                "type": "object",
                "properties": {
                    "region": {"type": "string", "description": "截图区域 x,y,width,height"},
                },
                "required": [],
            },
            handler=take_screenshot,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="locate_on_screen",
            description="在屏幕上定位图像",
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "查找图像路径"},
                    "confidence": {"type": "number", "description": "匹配置信度 0-1", "default": 0.9},
                },
                "required": ["image_path"],
            },
            handler=locate_on_screen,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="get_screen_size",
            description="获取屏幕分辨率",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_screen_size,
            security_level=SecurityLevel.READ_ONLY,
        ),
        # 剪贴板
        ToolDefinition(
            name="get_clipboard",
            description="获取剪贴板内容",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_clipboard,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="set_clipboard",
            description="设置剪贴板内容",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "剪贴板内容"},
                },
                "required": ["text"],
            },
            handler=set_clipboard,
            security_level=SecurityLevel.WRITE,
        ),
        # 计算
        ToolDefinition(
            name="calculate",
            description="安全计算数学表达式",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"},
                },
                "required": ["expression"],
            },
            handler=calculate,
            security_level=SecurityLevel.READ_ONLY,
        ),
    ]