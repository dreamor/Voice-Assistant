"""
通用工具注册 - Layer 1
跨平台纯 Python 工具（文件、系统、输入、屏幕、剪贴板、计算器、
窗口、浏览器、媒体、快捷操作、通知、文件高级、网络、显示）
"""
from voice_assistant.security.safe_guard import SecurityLevel
from voice_assistant.tools.registry import ToolDefinition
from voice_assistant.tools.universal.browser_ops import (
    open_url,
    search_web,
)
from voice_assistant.tools.universal.clipboard_ops import (
    get_clipboard,
    set_clipboard,
)
from voice_assistant.tools.universal.code_ops import (
    run_python_code,
)
from voice_assistant.tools.universal.display_ops import (
    get_brightness,
    get_display_info,
    set_brightness,
)
from voice_assistant.tools.universal.file_advanced_ops import (
    compress_files,
    copy_file,
    decompress_file,
    get_file_info,
    move_file,
    search_in_files,
)
from voice_assistant.tools.universal.file_ops import (
    delete_directory,
    delete_file,
    find_files,
    list_directory,
    read_file,
    write_file,
)
from voice_assistant.tools.universal.input_ops import (
    click_mouse,
    double_click,
    move_mouse,
    press_keys,
    right_click,
    scroll,
    type_text,
)
from voice_assistant.tools.universal.media_ops import (
    media_mute,
    media_next,
    media_play_pause,
    media_previous,
    media_volume_down,
    media_volume_up,
)
from voice_assistant.tools.universal.network_ops import (
    get_network_info,
    get_wifi_status,
    ping_host,
)
from voice_assistant.tools.universal.notification_ops import (
    set_reminder,
)
from voice_assistant.tools.universal.screen_ops import (
    get_screen_size,
    locate_on_screen,
    take_screenshot,
)
from voice_assistant.tools.universal.shortcut_ops import (
    open_spotlight,
    restart_computer,
    shutdown_computer,
    sleep_display,
    take_screenshot_to_clipboard,
)
from voice_assistant.tools.universal.system_ops import (
    get_active_window_title,
    get_running_processes,
    get_system_info,
    kill_process,
)
from voice_assistant.tools.universal.utility_ops import (
    calculate,
)
from voice_assistant.tools.universal.window_ops import (
    close_window,
    focus_window,
    list_windows,
    maximize_window,
    minimize_window,
    move_window_to_center,
    resize_window,
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
        # 代码执行（兜底通用任务）
        ToolDefinition(
            name="run_python_code",
            description=(
                "执行一段 Python 代码并返回 stdout/stderr/返回码。"
                "用于在没有专用 tool 时完成数据处理、文件批操作、网络请求等任务。"
                "代码在独立子进程中运行，默认 30 秒超时（最大 120 秒）。"
                "需要用户确认后才执行。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "完整 Python 源码。可使用标准库及项目已安装的第三方包 (requests, pydub, PIL, psutil 等)。",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "最大执行秒数 (1-120, 默认 30)",
                        "default": 30,
                    },
                },
                "required": ["code"],
            },
            handler=run_python_code,
            security_level=SecurityLevel.DANGEROUS,
        ),
        # 窗口管理
        ToolDefinition(
            name="list_windows",
            description="列出所有可见窗口（标题+PID）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=list_windows,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="focus_window",
            description="按标题关键词聚焦窗口",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "窗口标题关键词"},
                },
                "required": ["title"],
            },
            handler=focus_window,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="minimize_window",
            description="最小化窗口（空标题则最小化当前窗口）",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "窗口标题关键词（留空操作当前窗口）", "default": ""},
                },
                "required": [],
            },
            handler=minimize_window,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="maximize_window",
            description="最大化窗口（空标题则最大化当前窗口）",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "窗口标题关键词（留空操作当前窗口）", "default": ""},
                },
                "required": [],
            },
            handler=maximize_window,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="close_window",
            description="关闭窗口（空标题则关闭当前窗口）",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "窗口标题关键词（留空操作当前窗口）", "default": ""},
                },
                "required": [],
            },
            handler=close_window,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="resize_window",
            description="设置窗口位置和大小",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X 坐标"},
                    "y": {"type": "integer", "description": "Y 坐标"},
                    "width": {"type": "integer", "description": "宽度"},
                    "height": {"type": "integer", "description": "高度"},
                    "title": {"type": "string", "description": "窗口标题关键词（留空操作当前窗口）", "default": ""},
                },
                "required": ["x", "y", "width", "height"],
            },
            handler=resize_window,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="move_window_to_center",
            description="将窗口居中显示（空标题则操作当前窗口）",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "窗口标题关键词（留空操作当前窗口）", "default": ""},
                },
                "required": [],
            },
            handler=move_window_to_center,
            security_level=SecurityLevel.WRITE,
        ),
        # 浏览器操作
        ToolDefinition(
            name="open_url",
            description="用默认浏览器打开 URL",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL 地址"},
                },
                "required": ["url"],
            },
            handler=open_url,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="search_web",
            description="用默认浏览器搜索关键词",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "engine": {
                        "type": "string",
                        "description": "搜索引擎: google/bing/baidu/duckduckgo",
                        "default": "google",
                    },
                },
                "required": ["query"],
            },
            handler=search_web,
            security_level=SecurityLevel.READ_ONLY,
        ),
        # 媒体控制
        ToolDefinition(
            name="media_play_pause",
            description="播放/暂停媒体",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=media_play_pause,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="media_next",
            description="下一曲",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=media_next,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="media_previous",
            description="上一曲",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=media_previous,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="media_volume_up",
            description="音量加",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=media_volume_up,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="media_volume_down",
            description="音量减",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=media_volume_down,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="media_mute",
            description="静音切换",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=media_mute,
            security_level=SecurityLevel.WRITE,
        ),
        # 系统快捷操作
        ToolDefinition(
            name="sleep_display",
            description="关闭显示器（休眠显示）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=sleep_display,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="restart_computer",
            description="重启电脑",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=restart_computer,
            security_level=SecurityLevel.DANGEROUS,
        ),
        ToolDefinition(
            name="shutdown_computer",
            description="关闭电脑",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=shutdown_computer,
            security_level=SecurityLevel.DANGEROUS,
        ),
        ToolDefinition(
            name="take_screenshot_to_clipboard",
            description="截图到剪贴板（不保存文件）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=take_screenshot_to_clipboard,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="open_spotlight",
            description="打开系统搜索/Launcher（Spotlight/开始菜单）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=open_spotlight,
            security_level=SecurityLevel.READ_ONLY,
        ),
        # 通知提醒
        ToolDefinition(
            name="set_reminder",
            description="设置定时提醒（秒数+标题+消息），到时间后弹出系统通知",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "提醒标题"},
                    "message": {"type": "string", "description": "提醒内容"},
                    "seconds": {"type": "integer", "description": "延迟秒数（1-86400）"},
                },
                "required": ["title", "message", "seconds"],
            },
            handler=set_reminder,
            security_level=SecurityLevel.WRITE,
        ),
        # 文件高级操作
        ToolDefinition(
            name="search_in_files",
            description="在文件内容中搜索关键词（grep）",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "搜索关键词"},
                    "directory": {"type": "string", "description": "搜索目录", "default": "."},
                    "file_ext": {"type": "string", "description": "文件扩展名过滤（不含点号）", "default": ""},
                },
                "required": ["pattern"],
            },
            handler=search_in_files,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="move_file",
            description="移动或重命名文件/目录",
            parameters={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "源路径"},
                    "destination": {"type": "string", "description": "目标路径"},
                },
                "required": ["source", "destination"],
            },
            handler=move_file,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="copy_file",
            description="复制文件或目录",
            parameters={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "源路径"},
                    "destination": {"type": "string", "description": "目标路径"},
                },
                "required": ["source", "destination"],
            },
            handler=copy_file,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="compress_files",
            description="压缩文件或目录为 zip",
            parameters={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "要压缩的文件或目录路径"},
                    "output": {"type": "string", "description": "输出 zip 路径（留空则自动生成）", "default": ""},
                },
                "required": ["source"],
            },
            handler=compress_files,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="decompress_file",
            description="解压 zip 文件",
            parameters={
                "type": "object",
                "properties": {
                    "zip_path": {"type": "string", "description": "zip 文件路径"},
                    "output_dir": {"type": "string", "description": "解压目录（留空则解压到同目录）", "default": ""},
                },
                "required": ["zip_path"],
            },
            handler=decompress_file,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="get_file_info",
            description="获取文件元信息（大小、修改时间、权限等）",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                },
                "required": ["path"],
            },
            handler=get_file_info,
            security_level=SecurityLevel.READ_ONLY,
        ),
        # 网络操作
        ToolDefinition(
            name="get_network_info",
            description="获取网络连接信息（IP、网关、DNS）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_network_info,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="get_wifi_status",
            description="获取当前 WiFi 连接信息",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_wifi_status,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="ping_host",
            description="ping 指定主机",
            parameters={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "主机地址"},
                    "count": {"type": "integer", "description": "ping 次数 (1-10)", "default": 4},
                },
                "required": ["host"],
            },
            handler=ping_host,
            security_level=SecurityLevel.READ_ONLY,
        ),
        # 显示控制
        ToolDefinition(
            name="get_display_info",
            description="获取显示器信息（数量、分辨率）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_display_info,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="set_brightness",
            description="调节屏幕亮度 (0-100)",
            parameters={
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "亮度级别 0-100"},
                },
                "required": ["level"],
            },
            handler=set_brightness,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="get_brightness",
            description="获取当前屏幕亮度",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_brightness,
            security_level=SecurityLevel.READ_ONLY,
        ),
    ]
