"""
通用输入操作工具 - input_ops
鼠标移动/点击、键盘输入、滚动等
"""
import logging
import time
import platform

logger = logging.getLogger(__name__)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


def _check_pyautogui() -> str | None:
    if not HAS_PYAUTOGUI:
        return "需要安装 pyautogui: pip install pyautogui"
    return None


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
    """键盘输入文本"""
    err = _check_pyautogui()
    if err:
        return err
    try:
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
        pyautogui.hotkey(*keys)
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