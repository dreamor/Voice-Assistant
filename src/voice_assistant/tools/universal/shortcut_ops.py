"""
通用系统快捷操作工具 - shortcut_ops
锁屏（已存在于平台 ops）、休眠显示器、重启/关机、截图到剪贴板、打开搜索
"""
import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

_SHUTDOWN_DELAY_SEC = 60


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _is_win() -> bool:
    return platform.system() == "Windows"


def sleep_display() -> str:
    """关闭显示器（休眠显示）"""
    if _is_mac():
        try:
            subprocess.run(["pmset", "displaysleepnow"], capture_output=True, timeout=5)
            return "显示器已休眠"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"显示器休眠失败: {e}"
    elif _is_win():
        try:
            ps_cmd = (
                "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
                "public class Monitor{[DllImport(\"user32.dll\")]"
                "public static extern int SendMessage(IntPtr hWnd,int Msg,int wParam,int lParam);}';"
                "[Monitor]::SendMessage([IntPtr]0xffff,0x0112,0xF170,2)"
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            return "显示器已休眠"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"显示器休眠失败: {e}"
    return "当前平台不支持显示器休眠操作"


def restart_computer() -> str:
    """重启电脑（60 秒延迟，可用 `sudo killall shutdown` 或 `shutdown /a` 取消）"""
    delay_min = max(1, _SHUTDOWN_DELAY_SEC // 60)
    if _is_mac():
        try:
            subprocess.run(
                ["sudo", "-n", "shutdown", "-r", f"+{delay_min}"],
                capture_output=True, text=True, timeout=10,
            )
            return f"将在 {delay_min} 分钟后重启（取消: sudo killall shutdown）"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"重启失败: {e}"
    elif _is_win():
        try:
            subprocess.run(
                ["shutdown", "/r", "/t", str(_SHUTDOWN_DELAY_SEC)],
                capture_output=True, text=True, timeout=10,
            )
            return f"将在 {_SHUTDOWN_DELAY_SEC} 秒后重启（取消: shutdown /a）"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"重启失败: {e}"
    return "当前平台不支持重启操作"


def shutdown_computer() -> str:
    """关闭电脑（60 秒延迟，可用 `sudo killall shutdown` 或 `shutdown /a` 取消）"""
    delay_min = max(1, _SHUTDOWN_DELAY_SEC // 60)
    if _is_mac():
        try:
            subprocess.run(
                ["sudo", "-n", "shutdown", "-h", f"+{delay_min}"],
                capture_output=True, text=True, timeout=10,
            )
            return f"将在 {delay_min} 分钟后关机（取消: sudo killall shutdown）"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"关机失败: {e}"
    elif _is_win():
        try:
            subprocess.run(
                ["shutdown", "/s", "/t", str(_SHUTDOWN_DELAY_SEC)],
                capture_output=True, text=True, timeout=10,
            )
            return f"将在 {_SHUTDOWN_DELAY_SEC} 秒后关机（取消: shutdown /a）"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"关机失败: {e}"
    return "当前平台不支持关机操作"


def take_screenshot_to_clipboard() -> str:
    """截图到剪贴板（不保存文件）"""
    if _is_mac():
        try:
            subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to keystroke "3" using {command down, shift down, control down}'],
                capture_output=True, text=True, timeout=10
            )
            return "截图已复制到剪贴板"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"截图到剪贴板失败: {e}"
    elif _is_win():
        try:
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "[System.Windows.Forms.SendKeys]::SendWait('{PRTSC}')"
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            return "截图已复制到剪贴板"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"截图到剪贴板失败: {e}"
    return "当前平台不支持截图到剪贴板"


def open_spotlight() -> str:
    """打开系统搜索/Launcher"""
    if _is_mac():
        try:
            subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to keystroke " " using {command down}'],
                capture_output=True, text=True, timeout=5
            )
            return "已打开 Spotlight"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"打开 Spotlight 失败: {e}"
    elif _is_win():
        try:
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "[System.Windows.Forms.SendKeys]::SendWait('^{ESC}')"
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5
            )
            return "已打开搜索"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"打开搜索失败: {e}"
    return "当前平台不支持打开搜索操作"
