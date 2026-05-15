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
except ImportError:
    HAS_PYAUTOGUI = False


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _media_key(key: str) -> str:
    """通过 pyautogui 发送媒体键，回退到 AppleScript"""
    if HAS_PYAUTOGUI:
        try:
            pyautogui.press(key)
            return ""
        except (OSError, RuntimeError):
            pass
    if _is_mac():
        key_map = {
            "playpause": "key code 16",
            "nexttrack": "key code 17",
            "prevtrack": "key code 18",
            "volumeup": "key code 72",
            "volumedown": "key code 73",
            "volumemute": "key code 74",
        }
        cmd = key_map.get(key)
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
