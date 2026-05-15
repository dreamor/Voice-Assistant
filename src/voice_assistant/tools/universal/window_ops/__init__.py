"""
通用窗口操作工具 - window_ops
列出、聚焦、最小化、最大化、关闭、调整窗口
Mac 用 AppleScript，Windows 用 pywin32（可选）
"""
import platform

from . import _mac, _win


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _is_win() -> bool:
    return platform.system() == "Windows"


def list_windows() -> str:
    """列出所有可见窗口（标题 + PID）"""
    if _is_mac():
        return _mac.list_windows()
    if _is_win():
        return _win.list_windows()
    return "当前平台不支持窗口列表操作"


def focus_window(title: str) -> str:
    """按标题关键词聚焦窗口"""
    if _is_mac():
        return _mac.focus_window(title)
    if _is_win():
        return _win.focus_window(title)
    return "当前平台不支持窗口聚焦操作"


def minimize_window(title: str = "") -> str:
    """最小化窗口（空标题则最小化当前活跃窗口）"""
    if _is_mac():
        return _mac.minimize_window(title)
    if _is_win():
        return _win.minimize_window(title)
    return "当前平台不支持窗口最小化操作"


def maximize_window(title: str = "") -> str:
    """最大化窗口（空标题则最大化当前活跃窗口）"""
    if _is_mac():
        return _mac.maximize_window(title)
    if _is_win():
        return _win.maximize_window(title)
    return "当前平台不支持窗口最大化操作"


def close_window(title: str = "") -> str:
    """关闭窗口（空标题则关闭当前活跃窗口）"""
    if _is_mac():
        return _mac.close_window(title)
    if _is_win():
        return _win.close_window(title)
    return "当前平台不支持关闭窗口操作"


def resize_window(x: int, y: int, width: int, height: int, title: str = "") -> str:
    """设置窗口位置和大小（空标题则操作当前活跃窗口）"""
    if _is_mac():
        return _mac.resize_window(x, y, width, height, title)
    if _is_win():
        return _win.resize_window(x, y, width, height, title)
    return "当前平台不支持调整窗口操作"


def move_window_to_center(title: str = "") -> str:
    """将窗口居中显示（空标题则操作当前活跃窗口）"""
    if _is_mac():
        return _mac.center_window(title)
    if _is_win():
        return _win.center_window(title)
    return "当前平台不支持窗口居中操作"


__all__ = [
    "list_windows",
    "focus_window",
    "minimize_window",
    "maximize_window",
    "close_window",
    "resize_window",
    "move_window_to_center",
]
