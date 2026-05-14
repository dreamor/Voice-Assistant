"""
macOS 平台特定工具 - mac_ops
AppleScript / osascript 实现的系统操作
"""
import logging
import os
import subprocess

from voice_assistant.security.safe_guard import SecurityLevel
from voice_assistant.tools.registry import ToolDefinition

logger = logging.getLogger(__name__)


def set_system_volume(level: int) -> str:
    """设置系统音量 (0-100)"""
    level = max(0, min(100, level))
    try:
        result = subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"音量已设置为 {level}%"
        return f"设置音量失败: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "设置音量超时"
    except Exception as e:
        return f"设置音量失败: {e}"


def toggle_dark_mode() -> str:
    """切换深色/浅色模式"""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to tell appearance preferences to set dark mode to not dark mode'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return "已切换深色/浅色模式"
        return f"切换失败: {result.stderr}"
    except Exception as e:
        return f"切换深色模式失败: {e}"


def toggle_bluetooth() -> str:
    """切换蓝牙开关"""
    try:
        subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to tell process "SystemUIServer" '
             'to click menu item "Bluetooth" of menu "Status Bar" of menu bar item "Bluetooth" of menu bar 1'],
            capture_output=True, text=True, timeout=10
        )
        return "已请求切换蓝牙（请手动确认）"
    except Exception as e:
        return f"切换蓝牙失败: {e}"


def toggle_wifi() -> str:
    """切换 Wi-Fi 开关"""
    try:
        result = subprocess.run(
            ["networksetup", "-getairportpower", "en0"],
            capture_output=True, text=True, timeout=10
        )
        is_on = "On" in result.stdout
        new_state = "Off" if is_on else "On"
        subprocess.run(
            ["networksetup", "-setairportpower", "en0", new_state],
            capture_output=True, text=True, timeout=10
        )
        return f"Wi-Fi 已{'关闭' if is_on else '开启'}"
    except Exception as e:
        return f"切换 Wi-Fi 失败: {e}"


def empty_trash() -> str:
    """清空回收站"""
    try:
        result = subprocess.run(
            ["osascript", "-e", 'tell application "Finder" to empty trash'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return "回收站已清空"
        return f"清空回收站失败: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "清空回收站超时"
    except Exception as e:
        return f"清空回收站失败: {e}"


def set_wallpaper(path: str) -> str:
    """设置桌面壁纸"""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             f'tell application "System Events" to set picture of every desktop to POSIX file "{path}"'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"壁纸已设置: {path}"
        return f"设置壁纸失败: {result.stderr}"
    except Exception as e:
        return f"设置壁纸失败: {e}"


def lock_screen() -> str:
    """锁定屏幕"""
    try:
        subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "q" using {control down, command down}'],
            capture_output=True, text=True, timeout=5
        )
        return "已锁定屏幕"
    except Exception as e:
        return f"锁定屏幕失败: {e}"


def get_battery() -> str:
    """获取电池信息"""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return "未检测到电池"
        status = "充电中" if battery.power_plugged else "使用电池"
        remaining = ""
        if not battery.power_plugged and battery.secs_left > 0:
            hours, remainder = divmod(battery.secs_left, 3600)
            minutes = remainder // 60
            remaining = f"，剩余 {int(hours)}小时{int(minutes)}分钟"
        return f"电池: {battery.percent}% ({status}{remaining})"
    except ImportError:
        return "需要安装 psutil: pip install psutil"
    except Exception as e:
        return f"获取电池信息失败: {e}"


def show_notification(title: str, message: str) -> str:
    """显示系统通知"""
    try:
        escaped_title = title.replace('"', '\\"')
        escaped_message = message.replace('"', '\\"')
        result = subprocess.run(
            ["osascript", "-e",
             f'display notification "{escaped_message}" with title "{escaped_title}"'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"通知已发送: {title}"
        return f"发送通知失败: {result.stderr}"
    except Exception as e:
        return f"发送通知失败: {e}"


def run_shortcut(name: str) -> str:
    """运行快捷指令"""
    try:
        result = subprocess.run(
            ["shortcuts", "run", name],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return f"快捷指令 '{name}' 已执行"
        return f"执行快捷指令失败: {result.stderr}"
    except subprocess.TimeoutExpired:
        return f"快捷指令 '{name}' 执行超时"
    except FileNotFoundError:
        return "快捷指令不可用（需要 macOS 12+）"
    except Exception as e:
        return f"执行快捷指令失败: {e}"


def launch_application(app_name: str) -> str:
    """启动应用程序"""
    try:
        result = subprocess.run(
            ["open", "-a", app_name],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return f"已启动应用: {app_name}"
        return f"启动应用失败: {result.stderr.strip() or '未找到该应用'}"
    except subprocess.TimeoutExpired:
        return f"启动应用超时: {app_name}"
    except Exception as e:
        return f"启动应用失败: {e}"


def open_file(file_path: str) -> str:
    """用默认应用打开文件或文件夹"""
    expanded = os.path.expanduser(file_path)
    if not os.path.exists(expanded):
        return f"文件不存在: {file_path}"
    try:
        result = subprocess.run(
            ["open", expanded],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return f"已打开: {file_path}"
        return f"打开失败: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return f"打开超时: {file_path}"
    except Exception as e:
        return f"打开失败: {e}"


def quit_application(app_name: str) -> str:
    """退出应用程序"""
    escaped = app_name.replace('"', '\\"')
    try:
        result = subprocess.run(
            ["osascript", "-e", f'quit application "{escaped}"'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"已退出应用: {app_name}"
        return f"退出应用失败: {result.stderr.strip() or '应用未运行'}"
    except subprocess.TimeoutExpired:
        return f"退出应用超时: {app_name}"
    except Exception as e:
        return f"退出应用失败: {e}"


def is_application_running(app_name: str) -> str:
    """检查应用是否正在运行"""
    escaped = app_name.replace('"', '\\"')
    try:
        result = subprocess.run(
            ["osascript", "-e", f'application "{escaped}" is running'],
            capture_output=True, text=True, timeout=10
        )
        if "true" in (result.stdout or "").lower():
            return f"{app_name} 正在运行"
        return f"{app_name} 未运行"
    except subprocess.TimeoutExpired:
        return f"检查应用状态超时: {app_name}"
    except Exception as e:
        return f"检查应用状态失败: {e}"


def get_mac_tools() -> list[ToolDefinition]:
    """返回 macOS 平台特定工具"""
    return [
        ToolDefinition(
            name="launch_application",
            description="启动应用程序，如 Calculator、Safari、Chrome 等",
            parameters={
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "应用名称，如 Calculator、Safari、Chrome、TextEdit"}},
                "required": ["app_name"],
            },
            handler=launch_application,
            security_level=SecurityLevel.READ_ONLY,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="open_file",
            description="用默认应用打开文件或文件夹，支持 ~/Desktop 等路径",
            parameters={
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "文件或文件夹路径，如 ~/Desktop/report.xlsx、/Users/用户名/Documents"}},
                "required": ["file_path"],
            },
            handler=open_file,
            security_level=SecurityLevel.READ_ONLY,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="set_system_volume",
            description="设置系统音量 (0-100)",
            parameters={
                "type": "object",
                "properties": {"level": {"type": "integer", "description": "音量级别 0-100"}},
                "required": ["level"],
            },
            handler=set_system_volume,
            security_level=SecurityLevel.WRITE,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="toggle_dark_mode",
            description="切换深色/浅色模式",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=toggle_dark_mode,
            security_level=SecurityLevel.WRITE,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="toggle_bluetooth",
            description="切换蓝牙开关",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=toggle_bluetooth,
            security_level=SecurityLevel.WRITE,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="toggle_wifi",
            description="切换 Wi-Fi 开关",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=toggle_wifi,
            security_level=SecurityLevel.WRITE,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="empty_trash",
            description="清空回收站",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=empty_trash,
            security_level=SecurityLevel.DANGEROUS,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="set_wallpaper",
            description="设置桌面壁纸",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "壁纸图片路径"}},
                "required": ["path"],
            },
            handler=set_wallpaper,
            security_level=SecurityLevel.WRITE,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="lock_screen",
            description="锁定屏幕",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lock_screen,
            security_level=SecurityLevel.WRITE,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="get_battery",
            description="获取电池信息",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_battery,
            security_level=SecurityLevel.READ_ONLY,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="show_notification",
            description="显示系统通知",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "通知标题"},
                    "message": {"type": "string", "description": "通知内容"},
                },
                "required": ["title", "message"],
            },
            handler=show_notification,
            security_level=SecurityLevel.WRITE,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="run_shortcut",
            description="运行快捷指令",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "快捷指令名称"}},
                "required": ["name"],
            },
            handler=run_shortcut,
            security_level=SecurityLevel.WRITE,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="quit_application",
            description="退出应用程序",
            parameters={
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "应用名称，如 Safari、Chrome"}},
                "required": ["app_name"],
            },
            handler=quit_application,
            security_level=SecurityLevel.DANGEROUS,
            platforms=["mac"],
        ),
        ToolDefinition(
            name="is_application_running",
            description="检查应用是否正在运行",
            parameters={
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "应用名称"}},
                "required": ["app_name"],
            },
            handler=is_application_running,
            security_level=SecurityLevel.READ_ONLY,
            platforms=["mac"],
        ),
    ]
