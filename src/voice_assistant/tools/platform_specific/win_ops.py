"""
Windows 平台特定工具 - win_ops
PowerShell 实现的系统操作
"""
import logging
import subprocess

from voice_assistant.security.safe_guard import SecurityLevel
from voice_assistant.tools.registry import ToolDefinition

logger = logging.getLogger(__name__)

_BLOCKED_PS_COMMANDS = frozenset([
    "Remove-Item", "rm ", "del ", "Format-", "Stop-Computer",
    "Restart-Computer", "Remove-WindowsFeature", "net user", "net localgroup",
])


def set_system_volume(level: int) -> str:
    """设置系统音量 (0-100)"""
    level = max(0, min(100, level))
    try:
        ps_cmd = (
            f"$wshShell = New-Object -ComObject WScript.Shell; "
            f"1..50 | ForEach-Object {{$wshShell.SendKeys([char]174)}}; "
            f"1..{level // 2} | ForEach-Object {{$wshShell.SendKeys([char]175)}}"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
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
        ps_cmd = (
            "Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
            "Themes\\Personalize' -Name AppsUseLightTheme | Select-Object -ExpandProperty AppsUseLightTheme"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        is_light = "1" in result.stdout
        new_value = 0 if is_light else 1
        ps_cmd_set = (
            f"Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
            f"Themes\\Personalize' -Name AppsUseLightTheme -Value {new_value}; "
            f"Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
            f"Themes\\Personalize' -Name SystemUsesLightTheme -Value {new_value}"
        )
        subprocess.run(
            ["powershell", "-Command", ps_cmd_set],
            capture_output=True, text=True, timeout=10
        )
        return f"已切换为{'深色' if is_light else '浅色'}模式"
    except Exception as e:
        return f"切换深色模式失败: {e}"


def set_wallpaper(path: str) -> str:
    """设置桌面壁纸"""
    try:
        ps_cmd = (
            "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
            "public class Wallpaper{[DllImport(\"user32.dll\",CharSet=CharSet.Auto)]"
            "public static extern int SystemParametersInfo(int uAction,int uParam,string lpvParam,int fuWinIni);}';"
            f"[Wallpaper]::SystemParametersInfo(0x0014,0,'{path}',0x01 -bor 0x02)"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
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
            ["powershell", "-Command",
             "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
             "public class Lock{[DllImport(\"user32.dll\")]public static extern bool LockWorkStation();}';"
             "[Lock]::LockWorkStation()"],
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
        ps_cmd = (
            "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
            "$notify = New-Object System.Windows.Forms.NotifyIcon;"
            "$notify.Icon = [System.Drawing.SystemIcons]::Information;"
            "$notify.Visible = $true;"
            f"$notify.ShowBalloonTip(5000, '{title}', '{message}', 'Info')"
        )
        subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        return f"通知已发送: {title}"
    except Exception as e:
        return f"发送通知失败: {e}"


def set_display_mode(mode: str) -> str:
    """设置显示模式 (internal/external/extend/mirror)"""
    mode_map = {
        "internal": "/internal",
        "external": "/external",
        "extend": "/extend",
        "mirror": "/clone",
    }
    arg = mode_map.get(mode.lower())
    if not arg:
        return f"未知显示模式: {mode}，支持: internal, external, extend, mirror"
    try:
        subprocess.run(
            ["displayswitch.exe", arg],
            capture_output=True, text=True, timeout=10
        )
        return f"显示模式已设置为: {mode}"
    except FileNotFoundError:
        return "displayswitch.exe 不可用"
    except Exception as e:
        return f"设置显示模式失败: {e}"


def run_powershell_script(script: str) -> str:
    """执行 PowerShell 脚本（受限）"""
    for b in _BLOCKED_PS_COMMANDS:
        if b.lower() in script.lower():
            return f"不允许的操作: 包含被禁止的命令 '{b}'"
    try:
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip() if result.stdout else ""
        error = result.stderr.strip() if result.stderr else ""
        if result.returncode != 0:
            return f"执行失败 (exit {result.returncode}): {error or '未知错误'}"
        return output if output else "执行成功（无输出）"
    except subprocess.TimeoutExpired:
        return "脚本执行超时（30秒）"
    except Exception as e:
        return f"执行失败: {e}"


def get_win_tools() -> list[ToolDefinition]:
    """返回 Windows 平台特定工具"""
    return [
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
            platforms=["windows"],
        ),
        ToolDefinition(
            name="toggle_dark_mode",
            description="切换深色/浅色模式",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=toggle_dark_mode,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
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
            platforms=["windows"],
        ),
        ToolDefinition(
            name="lock_screen",
            description="锁定屏幕",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lock_screen,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="get_battery",
            description="获取电池信息",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_battery,
            security_level=SecurityLevel.READ_ONLY,
            platforms=["windows"],
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
            platforms=["windows"],
        ),
        ToolDefinition(
            name="set_display_mode",
            description="设置显示模式 (internal/external/extend/mirror)",
            parameters={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "显示模式: internal, external, extend, mirror",
                        "enum": ["internal", "external", "extend", "mirror"],
                    },
                },
                "required": ["mode"],
            },
            handler=set_display_mode,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="run_powershell_script",
            description="执行 PowerShell 脚本（受限，禁止危险命令）",
            parameters={
                "type": "object",
                "properties": {"script": {"type": "string", "description": "PowerShell 脚本内容"}},
                "required": ["script"],
            },
            handler=run_powershell_script,
            security_level=SecurityLevel.DANGEROUS,
            platforms=["windows"],
        ),
    ]
