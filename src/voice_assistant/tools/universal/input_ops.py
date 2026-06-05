"""
通用输入操作工具 - input_ops
鼠标移动/点击、键盘输入、滚动等
"""
import logging
import platform
import subprocess
import time

logger = logging.getLogger(__name__)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    HAS_PYAUTOGUI = True
except Exception:  # ImportError 或无头环境下的 KeyError('DISPLAY')
    HAS_PYAUTOGUI = False


def _check_pyautogui() -> str | None:
    if not HAS_PYAUTOGUI:
        return "需要安装 pyautogui: pip install pyautogui"
    return None


# Mac → Windows 键名映射（pyautogui 在 Windows 上不认识 Mac 键名）
_KEY_MAP_WINDOWS = {
    "command": "ctrl",
    "cmd": "ctrl",
    "option": "alt",
    "opt": "alt",
    "control": "ctrl",
    "return": "enter",
    "delete": "backspace",
}


def _normalize_keys(keys: tuple) -> tuple:
    """将 Mac 键名映射为当前平台对应的键名"""
    if platform.system() != "Windows":
        return keys
    return tuple(_KEY_MAP_WINDOWS.get(k.lower(), k) for k in keys)


def _type_text_via_clipboard(text: str) -> str:
    """通过剪贴板粘贴输入非 ASCII 文本（中文、日文等）"""
    system = platform.system()
    old_clipboard = ""
    try:
        # 保存当前剪贴板内容
        if system == "Darwin":
            result = subprocess.run(
                ["pbpaste"], capture_output=True, text=True, timeout=3
            )
            old_clipboard = result.stdout
        elif system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=3,
            )
            old_clipboard = result.stdout

        # 设置剪贴板为要输入的文本
        if system == "Darwin":
            subprocess.run(
                ["pbcopy"], input=text, text=True, timeout=3,
            )
            pyautogui.hotkey("command", "v")
        elif system == "Windows":
            safe = text.replace("'", "''")
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{safe}'"],
                capture_output=True, text=True, timeout=3,
            )
            pyautogui.hotkey("ctrl", "v")
        else:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text, text=True, timeout=3,
            )
            pyautogui.hotkey("ctrl", "v")

        # 等待粘贴完成
        time.sleep(0.15)

        # 恢复剪贴板
        if system == "Darwin":
            subprocess.run(
                ["pbcopy"], input=old_clipboard, text=True, timeout=3,
            )
        elif system == "Windows":
            safe_old = old_clipboard.replace("'", "''")
            subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{safe_old}'"],
                capture_output=True, text=True, timeout=3,
            )

        return f"已输入: {text}"
    except Exception as e:
        return f"输入失败: {e}"


def move_mouse(x: int, y: int) -> str:
    """移动鼠标到指定坐标"""
    err = _check_pyautogui()
    if err:
        return err
    try:
        pyautogui.moveTo(x, y)
        return f"鼠标已移动到 ({x}, {y})"
    except Exception as e:
        return f"移动鼠标失败: {e}"


def click_mouse(button: str = "left") -> str:
    """点击鼠标"""
    err = _check_pyautogui()
    if err:
        return err
    try:
        pyautogui.click(button=button)
        return f"已{button}键点击"
    except Exception as e:
        return f"点击失败: {e}"


def double_click() -> str:
    """双击鼠标"""
    err = _check_pyautogui()
    if err:
        return err
    try:
        pyautogui.doubleClick()
        return "已双击"
    except Exception as e:
        return f"双击失败: {e}"


def right_click() -> str:
    """右键点击"""
    err = _check_pyautogui()
    if err:
        return err
    try:
        pyautogui.rightClick()
        return "已右键点击"
    except Exception as e:
        return f"右键点击失败: {e}"


def type_text(text: str) -> str:
    """键盘输入文本（支持中文等非 ASCII 字符）"""
    err = _check_pyautogui()
    if err:
        return err
    try:
        # 检测是否有非 ASCII 字符（中文、日文、韩文等）
        if any(ord(c) > 127 for c in text):
            return _type_text_via_clipboard(text)
        pyautogui.write(text)
        return f"已输入: {text}"
    except Exception as e:
        return f"输入失败: {e}"


def press_keys(*keys: str) -> str:
    """按下组合键，如 press_keys("command", "c")"""
    err = _check_pyautogui()
    if err:
        return err
    try:
        normalized = _normalize_keys(keys)
        pyautogui.hotkey(*normalized)
        return f"已按下: {'+'.join(keys)}"
    except Exception as e:
        return f"按键失败: {e}"


def scroll(amount: int = -3) -> str:
    """滚动鼠标滚轮，amount 为正向上滚动"""
    err = _check_pyautogui()
    if err:
        return err
    try:
        pyautogui.scroll(amount)
        direction = "向上" if amount > 0 else "向下"
        return f"已{direction}滚动 {abs(amount)} 行"
    except Exception as e:
        return f"滚动失败: {e}"


def get_screen_size() -> str:
    """获取屏幕分辨率"""
    err = _check_pyautogui()
    if err:
        return err
    try:
        w, h = pyautogui.size()
        return f"屏幕分辨率: {w} x {h}"
    except Exception as e:
        return f"获取屏幕信息失败: {e}"
