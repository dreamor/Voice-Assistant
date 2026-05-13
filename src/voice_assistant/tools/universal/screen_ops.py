"""
通用屏幕操作工具 - screen_ops
截图、图像定位等（依赖 Pillow/pyautogui）
"""
import logging
import os
import tempfile
import time

logger = logging.getLogger(__name__)

try:
    from PIL import Image  # noqa: F401  availability check
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except Exception:  # ImportError 或无头环境下的 KeyError('DISPLAY')
    HAS_PYAUTOGUI = False


def _check_deps() -> str | None:
    """检查依赖是否可用"""
    if not HAS_PYAUTOGUI:
        return "需要安装 pyautogui: pip install pyautogui"
    if not HAS_PILLOW:
        return "需要安装 Pillow: pip install Pillow"
    return None


def take_screenshot(region: str | None = None) -> str:
    """截取屏幕截图

    Args:
        region: 可选区域 "x,y,width,height"，不传则为全屏
    """
    err = _check_deps()
    if err:
        return err
    try:
        if region:
            parts = [int(x.strip()) for x in region.split(",")]
            if len(parts) != 4:
                return "区域格式: x,y,width,height"
            img = pyautogui.screenshot(region=tuple(parts))
        else:
            img = pyautogui.screenshot()

        screenshot_dir = os.path.join(tempfile.gettempdir(), "voice_assistant_screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        filename = f"screenshot_{int(time.time())}.png"
        filepath = os.path.join(screenshot_dir, filename)
        img.save(filepath)

        w, h = img.size
        desc = f"截图已保存: {filepath} ({w}x{h})"
        if region:
            desc += f" 区域: {region}"
        return desc
    except Exception as e:
        return f"截图失败: {e}"


def locate_on_screen(image_path: str, confidence: float = 0.9) -> str:
    """在屏幕上定位图像

    Args:
        image_path: 要查找的图像文件路径
        confidence: 匹配置信度 0-1
    """
    err = _check_deps()
    if err:
        return err
    try:
        from pathlib import Path
        resolved = Path(image_path)
        if not resolved.exists():
            return f"图像文件不存在: {image_path}"

        location = pyautogui.locateOnScreen(str(resolved), confidence=confidence)
        if location:
            x, y, w, h = location
            center_x, center_y = pyautogui.center(location)
            return f"找到图像: 位置({x}, {y}) 大小({w}x{h}) 中心点({center_x}, {center_y})"
        return f"未在屏幕上找到匹配图像 (置信度: {confidence})"
    except pyautogui.ImageNotFoundException:
        return f"未在屏幕上找到匹配图像 (置信度: {confidence})"
    except Exception as e:
        return f"图像定位失败: {e}"


def get_screen_size() -> str:
    """获取屏幕分辨率"""
    if not HAS_PYAUTOGUI:
        return "需要安装 pyautogui: pip install pyautogui"
    try:
        w, h = pyautogui.size()
        return f"屏幕分辨率: {w} x {h}"
    except Exception as e:
        return f"获取屏幕信息失败: {e}"
