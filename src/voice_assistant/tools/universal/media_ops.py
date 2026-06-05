"""
通用媒体控制工具 - media_ops
播放/暂停、上下曲、音量调节
优先使用 pyautogui media key，不可用时回退到平台命令
"""
import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except Exception:  # ImportError 或无头环境 KeyError('DISPLAY')
    HAS_PYAUTOGUI = False


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _is_win() -> bool:
    return platform.system() == "Windows"


# Windows 媒体键虚拟键码 (Virtual Key Codes)
_WIN_VK_MEDIA = {
    "playpause": 0xB3,
    "nexttrack": 0xB0,
    "prevtrack": 0xB1,
    "volumeup": 0xAF,
    "volumedown": 0xAE,
    "volumemute": 0xAD,
}

# macOS AppleScript key code 映射
_MAC_KEY_MAP = {
    "playpause": "key code 16",
    "nexttrack": "key code 17",
    "prevtrack": "key code 18",
    "volumeup": "key code 72",
    "volumedown": "key code 73",
    "volumemute": "key code 74",
}


def _media_key(key: str) -> str:
    """通过 pyautogui 发送媒体键，回退到平台命令"""
    if HAS_PYAUTOGUI:
        try:
            pyautogui.press(key)
            return ""
        except (OSError, RuntimeError):
            pass
    if _is_mac():
        cmd = _MAC_KEY_MAP.get(key)
        if not cmd:
            return f"不支持的媒体键: {key}"
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "System Events" to {cmd}'],
                capture_output=True, text=True, timeout=5
            )
            return ""
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return str(e)
    elif _is_win():
        vk = _WIN_VK_MEDIA.get(key)
        if not vk:
            return f"不支持的媒体键: {key}"
        try:
            # 使用 user32.dll keybd_event 发送媒体键
            ps_cmd = (
                "Add-Type -TypeDefinition '"
                "using System;using System.Runtime.InteropServices;"
                "public class MediaKey{"
                "[DllImport(\"user32.dll\")]"
                "public static extern void keybd_event(byte vk,byte scan,int flags,IntPtr ex);"
                "}';"
                f"[MediaKey]::keybd_event({vk},0,0,[IntPtr]::Zero);"
                f"[MediaKey]::keybd_event({vk},0,2,[IntPtr]::Zero)"
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5
            )
            return ""
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return str(e)
    return "需要安装 pyautogui: pip install pyautogui"


def media_play_pause() -> str:
    """播放/暂停媒体"""
    err = _media_key("playpause")
    if err:
        return f"播放/暂停失败: {err}"
    return "已发送播放/暂停"


def media_next() -> str:
    """下一曲"""
    err = _media_key("nexttrack")
    if err:
        return f"下一曲失败: {err}"
    return "已切换下一曲"


def media_previous() -> str:
    """上一曲"""
    err = _media_key("prevtrack")
    if err:
        return f"上一曲失败: {err}"
    return "已切换上一曲"


def media_volume_up() -> str:
    """音量加"""
    err = _media_key("volumeup")
    if err:
        return f"音量加失败: {err}"
    return "音量已增加"


def media_volume_down() -> str:
    """音量减"""
    err = _media_key("volumedown")
    if err:
        return f"音量减失败: {err}"
    return "音量已减少"


def media_mute() -> str:
    """静音切换"""
    err = _media_key("volumemute")
    if err:
        return f"静音切换失败: {err}"
    return "已切换静音"
