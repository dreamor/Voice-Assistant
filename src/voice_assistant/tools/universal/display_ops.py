"""
通用显示控制工具 - display_ops
获取显示器信息、调节亮度
"""
import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _is_win() -> bool:
    return platform.system() == "Windows"


def get_display_info() -> str:
    """获取显示器信息（数量、分辨率）"""
    if _is_mac():
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True, timeout=10
            )
            lines = []
            for line in result.stdout.split("\n"):
                stripped = line.strip()
                if any(k in stripped for k in [
                    "Resolution", "Display Type", "Vendor", "Chipset",
                    "Main Display", "Online", "Mirror", "分辨率", "显示器类型"
                ]):
                    lines.append(stripped)
            if not lines:
                return "未检测到显示器信息"
            return "显示器信息:\n" + "\n".join(lines)
        except subprocess.TimeoutExpired:
            return "获取显示器信息超时"
        except (FileNotFoundError, OSError) as e:
            return f"获取显示器信息失败: {e}"
    elif _is_win():
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject Win32_VideoController | "
                 "Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution | "
                 "Format-List"],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout.strip()
            if output:
                return "显示器信息:\n" + output
            return "未检测到显示器信息"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"获取显示器信息失败: {e}"

    try:
        import pyautogui
        w, h = pyautogui.size()
        return f"显示器分辨率: {w}x{h}"
    except (ImportError, OSError):
        return "当前平台不支持获取显示器信息"


def set_brightness(level: int) -> str:
    """调节屏幕亮度 (0-100)"""
    level = max(0, min(100, level))
    if _is_mac():
        try:
            result = subprocess.run(
                ["brightness", "-l"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return "需要安装 brightness: brew install brightness"
            subprocess.run(
                ["brightness", str(level / 100)],
                capture_output=True, text=True, timeout=5
            )
            return f"亮度已设置为 {level}%"
        except FileNotFoundError:
            return "需要安装 brightness: brew install brightness"
        except (subprocess.TimeoutExpired, OSError) as e:
            return f"设置亮度失败: {e}"
    elif _is_win():
        try:
            ps_cmd = (
                "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
                "public class Brightness{[DllImport(\"user32.dll\")]"
                "public static extern IntPtr SendMessage(IntPtr hWnd,int Msg,IntPtr wParam,IntPtr lParam);}';"
                f"[Brightness]::SendMessage([IntPtr]0xffff,0x0112,[IntPtr]0xf170,[IntPtr]{level})"
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            return f"亮度已设置为 {level}%"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"设置亮度失败: {e}"
    return "当前平台不支持亮度调节"


def get_brightness() -> str:
    """获取当前屏幕亮度"""
    if _is_mac():
        try:
            result = subprocess.run(
                ["brightness", "-l"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return "需要安装 brightness: brew install brightness"
            for line in result.stdout.split("\n"):
                if "brightness" in line.lower():
                    return line.strip()
            return result.stdout.strip() or "无法获取亮度"
        except FileNotFoundError:
            return "需要安装 brightness: brew install brightness"
        except (subprocess.TimeoutExpired, OSError) as e:
            return f"获取亮度失败: {e}"
    elif _is_win():
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness | "
                 "Select-Object CurrentBrightness | Format-List"],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout.strip()
            if output:
                return "当前亮度:\n" + output
            return "无法获取亮度（可能需要管理员权限）"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return f"获取亮度失败: {e}"
    return "当前平台不支持获取亮度"
