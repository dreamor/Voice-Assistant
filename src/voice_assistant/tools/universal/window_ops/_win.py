"""窗口操作 - Windows 实现 (pywin32)"""
import logging

logger = logging.getLogger(__name__)

_HAS_WIN32 = False
try:
    import win32con  # noqa: F401
    import win32gui  # noqa: F401
    _HAS_WIN32 = True
except ImportError:
    pass

_NO_WIN32_MSG = "需要安装 pywin32: pip install pywin32"


def list_windows() -> str:
    if not _HAS_WIN32:
        return _NO_WIN32_MSG
    try:
        import win32gui

        windows = []

        def _enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append(title)

        win32gui.EnumWindows(_enum_cb, None)
        if not windows:
            return "没有可见窗口"
        return "可见窗口列表:\n" + "\n".join(windows)
    except OSError as e:
        return f"获取窗口列表失败: {e}"


def focus_window(title: str) -> str:
    if not _HAS_WIN32:
        return _NO_WIN32_MSG
    try:
        import win32con
        import win32gui

        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            hwnd_found = [0]

            def _find_cb(h, _):
                t = win32gui.GetWindowText(h)
                if title.lower() in t.lower() and win32gui.IsWindowVisible(h):
                    hwnd_found[0] = h
                    return False
                return True

            win32gui.EnumWindows(_find_cb, None)
            hwnd = hwnd_found[0]

        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return f"已聚焦窗口: {title}"
        return f"未找到包含「{title}」的窗口"
    except OSError as e:
        return f"聚焦窗口失败: {e}"


def _resolve_hwnd(title: str):
    import win32gui
    if title:
        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            return None
        return hwnd
    return win32gui.GetForegroundWindow()


def minimize_window(title: str) -> str:
    if not _HAS_WIN32:
        return _NO_WIN32_MSG
    try:
        import win32con
        import win32gui
        hwnd = _resolve_hwnd(title)
        if hwnd is None:
            return f"未找到窗口: {title}"
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return "已最小化窗口"
    except OSError as e:
        return f"最小化窗口失败: {e}"


def maximize_window(title: str) -> str:
    if not _HAS_WIN32:
        return _NO_WIN32_MSG
    try:
        import win32con
        import win32gui
        hwnd = _resolve_hwnd(title)
        if hwnd is None:
            return f"未找到窗口: {title}"
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return "已最大化窗口"
    except OSError as e:
        return f"最大化窗口失败: {e}"


def close_window(title: str) -> str:
    if not _HAS_WIN32:
        return _NO_WIN32_MSG
    try:
        import win32con
        import win32gui
        hwnd = _resolve_hwnd(title)
        if hwnd is None:
            return f"未找到窗口: {title}"
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return "已关闭窗口"
    except OSError as e:
        return f"关闭窗口失败: {e}"


def resize_window(x: int, y: int, width: int, height: int, title: str) -> str:
    if not _HAS_WIN32:
        return _NO_WIN32_MSG
    try:
        import win32gui
        hwnd = _resolve_hwnd(title)
        if hwnd is None:
            return f"未找到窗口: {title}"
        win32gui.MoveWindow(hwnd, x, y, width, height, True)
        return f"窗口已调整: 位置({x},{y}) 大小({width}x{height})"
    except OSError as e:
        return f"调整窗口失败: {e}"


def center_window(title: str) -> str:
    if not _HAS_WIN32:
        return _NO_WIN32_MSG
    try:
        import win32api
        import win32con
        import win32gui

        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        hwnd = _resolve_hwnd(title)
        if hwnd is None:
            return f"未找到窗口: {title}"
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        win32gui.MoveWindow(hwnd, x, y, w, h, True)
        return "窗口已居中"
    except OSError as e:
        return f"窗口居中失败: {e}"
