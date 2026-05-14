"""
通用窗口操作工具 - window_ops
列出、聚焦、最小化、最大化、关闭、调整窗口
Mac 用 AppleScript，Windows 用 pywin32（可选）
"""
import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

_HAS_WIN32 = False
if platform.system() == "Windows":
    try:
        import win32gui  # noqa: F401
        import win32con  # noqa: F401
        _HAS_WIN32 = True
    except ImportError:
        pass


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _is_win() -> bool:
    return platform.system() == "Windows"


# ── 窗口列表 ──────────────────────────────────────────────

def list_windows() -> str:
    """列出所有可见窗口（标题 + PID）"""
    if _is_mac():
        return _list_windows_mac()
    elif _is_win():
        return _list_windows_win()
    return "当前平台不支持窗口列表操作"


def _list_windows_mac() -> str:
    try:
        script = (
            'tell application "System Events"\n'
            '  set output to ""\n'
            '  repeat with proc in (every process whose background only is false)\n'
            '    try\n'
            '      set procName to name of proc\n'
            '      set procId to unix id of proc\n'
            '      repeat with w in (every window of proc)\n'
            '        set winTitle to name of w\n'
            '        set output to output & procName & " | PID:" & procId & " | " & winTitle & "\\n"\n'
            '      end repeat\n'
            '    end try\n'
            '  end repeat\n'
            '  return output\n'
            'end tell'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            if not lines:
                return "没有可见窗口"
            return "可见窗口列表:\n" + "\n".join(lines)
        return "获取窗口列表失败"
    except subprocess.TimeoutExpired:
        return "获取窗口列表超时"
    except Exception as e:
        return f"获取窗口列表失败: {e}"


def _list_windows_win() -> str:
    if not _HAS_WIN32:
        return "需要安装 pywin32: pip install pywin32"
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
    except Exception as e:
        return f"获取窗口列表失败: {e}"


# ── 聚焦窗口 ──────────────────────────────────────────────

def focus_window(title: str) -> str:
    """按标题关键词聚焦窗口"""
    if _is_mac():
        return _focus_window_mac(title)
    elif _is_win():
        return _focus_window_win(title)
    return "当前平台不支持窗口聚焦操作"


def _focus_window_mac(title: str) -> str:
    escaped = title.replace('"', '\\"')
    try:
        script = (
            'tell application "System Events"\n'
            '  set found to false\n'
            '  repeat with proc in (every process whose background only is false)\n'
            '    try\n'
            '      repeat with w in (every window of proc)\n'
            '        if name of w contains "' + escaped + '" then\n'
            '          set frontmost of proc to true\n'
            '          set found to true\n'
            '          exit repeat\n'
            '        end if\n'
            '      end repeat\n'
            '    end try\n'
            '    if found then exit repeat\n'
            '  end repeat\n'
            '  return found\n'
            'end tell'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if "true" in (result.stdout or "").lower():
            return f"已聚焦窗口: {title}"
        return f"未找到包含「{title}」的窗口"
    except subprocess.TimeoutExpired:
        return "聚焦窗口超时"
    except Exception as e:
        return f"聚焦窗口失败: {e}"


def _focus_window_win(title: str) -> str:
    if not _HAS_WIN32:
        return "需要安装 pywin32: pip install pywin32"
    try:
        import win32gui
        import win32con

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
    except Exception as e:
        return f"聚焦窗口失败: {e}"


# ── 最小化窗口 ──────────────────────────────────────────────

def minimize_window(title: str = "") -> str:
    """最小化窗口（空标题则最小化当前活跃窗口）"""
    if _is_mac():
        return _minimize_window_mac(title)
    elif _is_win():
        return _minimize_window_win(title)
    return "当前平台不支持窗口最小化操作"


def _minimize_window_mac(title: str) -> str:
    try:
        if title:
            escaped = title.replace('"', '\\"')
            script = (
                'tell application "System Events"\n'
                '  repeat with proc in (every process whose background only is false)\n'
                '    try\n'
                '      repeat with w in (every window of proc)\n'
                '        if name of w contains "' + escaped + '" then\n'
                '          set miniaturized of w to true\n'
                '          return "true"\n'
                '        end if\n'
                '      end repeat\n'
                '    end try\n'
                '  end repeat\n'
                '  return "false"\n'
                'end tell'
            )
        else:
            script = (
                'tell application "System Events"\n'
                '  set frontProc to first process whose frontmost is true\n'
                '  try\n'
                '    set miniaturized of every window of frontProc to true\n'
                '    return "true"\n'
                '  end try\n'
                '  return "false"\n'
                'end tell'
            )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if "true" in (result.stdout or "").lower():
            return "已最小化窗口"
        return "最小化窗口失败" if title else "没有可最小化的窗口"
    except Exception as e:
        return f"最小化窗口失败: {e}"


def _minimize_window_win(title: str) -> str:
    if not _HAS_WIN32:
        return "需要安装 pywin32: pip install pywin32"
    try:
        import win32gui
        import win32con

        if title:
            hwnd = win32gui.FindWindow(None, title)
            if not hwnd:
                return f"未找到窗口: {title}"
        else:
            hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return "已最小化窗口"
    except Exception as e:
        return f"最小化窗口失败: {e}"


# ── 最大化窗口 ──────────────────────────────────────────────

def maximize_window(title: str = "") -> str:
    """最大化窗口（空标题则最大化当前活跃窗口）"""
    if _is_mac():
        return _maximize_window_mac(title)
    elif _is_win():
        return _maximize_window_win(title)
    return "当前平台不支持窗口最大化操作"


def _maximize_window_mac(title: str) -> str:
    try:
        if title:
            escaped = title.replace('"', '\\"')
            script = (
                'tell application "System Events"\n'
                '  repeat with proc in (every process whose background only is false)\n'
                '    try\n'
                '      repeat with w in (every window of proc)\n'
                '        if name of w contains "' + escaped + '" then\n'
                '          set zoomed of w to true\n'
                '          return "true"\n'
                '        end if\n'
                '      end repeat\n'
                '    end try\n'
                '  end repeat\n'
                '  return "false"\n'
                'end tell'
            )
        else:
            script = (
                'tell application "System Events"\n'
                '  set frontProc to first process whose frontmost is true\n'
                '  try\n'
                '    set zoomed of every window of frontProc to true\n'
                '    return "true"\n'
                '  end try\n'
                '  return "false"\n'
                'end tell'
            )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if "true" in (result.stdout or "").lower():
            return "已最大化窗口"
        return "最大化窗口失败"
    except Exception as e:
        return f"最大化窗口失败: {e}"


def _maximize_window_win(title: str) -> str:
    if not _HAS_WIN32:
        return "需要安装 pywin32: pip install pywin32"
    try:
        import win32gui
        import win32con

        if title:
            hwnd = win32gui.FindWindow(None, title)
            if not hwnd:
                return f"未找到窗口: {title}"
        else:
            hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return "已最大化窗口"
    except Exception as e:
        return f"最大化窗口失败: {e}"


# ── 关闭窗口 ──────────────────────────────────────────────

def close_window(title: str = "") -> str:
    """关闭窗口（空标题则关闭当前活跃窗口）"""
    if _is_mac():
        return _close_window_mac(title)
    elif _is_win():
        return _close_window_win(title)
    return "当前平台不支持关闭窗口操作"


def _close_window_mac(title: str) -> str:
    try:
        if title:
            escaped = title.replace('"', '\\"')
            script = (
                'tell application "System Events"\n'
                '  repeat with proc in (every process whose background only is false)\n'
                '    try\n'
                '      repeat with w in (every window of proc)\n'
                '        if name of w contains "' + escaped + '" then\n'
                '          click button 1 of w\n'
                '          return "true"\n'
                '        end if\n'
                '      end repeat\n'
                '    end try\n'
                '  end repeat\n'
                '  return "false"\n'
                'end tell'
            )
        else:
            script = (
                'tell application "System Events"\n'
                '  set frontProc to first process whose frontmost is true\n'
                '  try\n'
                '    click button 1 of window 1 of frontProc\n'
                '    return "true"\n'
                '  end try\n'
                '  return "false"\n'
                'end tell'
            )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if "true" in (result.stdout or "").lower():
            return "已关闭窗口"
        return "关闭窗口失败"
    except Exception as e:
        return f"关闭窗口失败: {e}"


def _close_window_win(title: str) -> str:
    if not _HAS_WIN32:
        return "需要安装 pywin32: pip install pywin32"
    try:
        import win32gui
        import win32con

        if title:
            hwnd = win32gui.FindWindow(None, title)
            if not hwnd:
                return f"未找到窗口: {title}"
        else:
            hwnd = win32gui.GetForegroundWindow()
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return "已关闭窗口"
    except Exception as e:
        return f"关闭窗口失败: {e}"


# ── 调整窗口大小/位置 ──────────────────────────────────────

def resize_window(x: int, y: int, width: int, height: int, title: str = "") -> str:
    """设置窗口位置和大小（空标题则操作当前活跃窗口）"""
    if _is_mac():
        return _resize_window_mac(x, y, width, height, title)
    elif _is_win():
        return _resize_window_win(x, y, width, height, title)
    return "当前平台不支持调整窗口操作"


def _resize_window_mac(x: int, y: int, width: int, height: int, title: str) -> str:
    try:
        if title:
            escaped = title.replace('"', '\\"')
            script = (
                'tell application "System Events"\n'
                '  repeat with proc in (every process whose background only is false)\n'
                '    try\n'
                '      repeat with w in (every window of proc)\n'
                '        if name of w contains "' + escaped + '" then\n'
                f'          set bounds of w to {{{x}, {y}, {x + width}, {y + height}}}\n'
                '          return "true"\n'
                '        end if\n'
                '      end repeat\n'
                '    end try\n'
                '  end repeat\n'
                '  return "false"\n'
                'end tell'
            )
        else:
            script = (
                'tell application "System Events"\n'
                '  set frontProc to first process whose frontmost is true\n'
                '  try\n'
                f'    set bounds of window 1 of frontProc to {{{x}, {y}, {x + width}, {y + height}}}\n'
                '    return "true"\n'
                '  end try\n'
                '  return "false"\n'
                'end tell'
            )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if "true" in (result.stdout or "").lower():
            return f"窗口已调整: 位置({x},{y}) 大小({width}x{height})"
        return "调整窗口失败"
    except Exception as e:
        return f"调整窗口失败: {e}"


def _resize_window_win(x: int, y: int, width: int, height: int, title: str) -> str:
    if not _HAS_WIN32:
        return "需要安装 pywin32: pip install pywin32"
    try:
        import win32gui

        if title:
            hwnd = win32gui.FindWindow(None, title)
            if not hwnd:
                return f"未找到窗口: {title}"
        else:
            hwnd = win32gui.GetForegroundWindow()
        win32gui.MoveWindow(hwnd, x, y, width, height, True)
        return f"窗口已调整: 位置({x},{y}) 大小({width}x{height})"
    except Exception as e:
        return f"调整窗口失败: {e}"


# ── 窗口居中 ──────────────────────────────────────────────

def move_window_to_center(title: str = "") -> str:
    """将窗口居中显示（空标题则操作当前活跃窗口）"""
    if _is_mac():
        return _center_window_mac(title)
    elif _is_win():
        return _center_window_win(title)
    return "当前平台不支持窗口居中操作"


def _center_window_mac(title: str) -> str:
    try:
        import subprocess as sp
        screen_res = sp.run(
            ["osascript", "-e", 'tell application "Finder" to get bounds of window of desktop'],
            capture_output=True, text=True, timeout=5
        )
        if title:
            escaped = title.replace('"', '\\"')
            script = (
                'tell application "System Events"\n'
                '  set screenW to do shell script "system_profiler SPDisplaysDataType | '
                'grep Resolution | head -1 | awk \\"{print \\$2}\\""\n'
                '  set screenH to do shell script "system_profiler SPDisplaysDataType | '
                'grep Resolution | head -1 | awk \\"{print \\$4}\\""\n'
                '  repeat with proc in (every process whose background only is false)\n'
                '    try\n'
                '      repeat with w in (every window of proc)\n'
                '        if name of w contains "' + escaped + '" then\n'
                '          set {wx, wy, wr, wb} to bounds of w\n'
                '          set ww to wr - wx\n'
                '          set wh to wb - wy\n'
                '          set newX to (screenW - ww) / 2\n'
                '          set newY to (screenH - wh) / 2\n'
                '          set bounds of w to {newX, newY, newX + ww, newY + wh}\n'
                '          return "true"\n'
                '        end if\n'
                '      end repeat\n'
                '    end try\n'
                '  end repeat\n'
                '  return "false"\n'
                'end tell'
            )
        else:
            script = (
                'tell application "System Events"\n'
                '  set screenW to do shell script "system_profiler SPDisplaysDataType | '
                'grep Resolution | head -1 | awk \\"{print \\$2}\\""\n'
                '  set screenH to do shell script "system_profiler SPDisplaysDataType | '
                'grep Resolution | head -1 | awk \\"{print \\$4}\\""\n'
                '  set frontProc to first process whose frontmost is true\n'
                '  try\n'
                '    set {wx, wy, wr, wb} to bounds of window 1 of frontProc\n'
                '    set ww to wr - wx\n'
                '    set wh to wb - wy\n'
                '    set newX to (screenW - ww) / 2\n'
                '    set newY to (screenH - wh) / 2\n'
                '    set bounds of window 1 of frontProc to {newX, newY, newX + ww, newY + wh}\n'
                '    return "true"\n'
                '  end try\n'
                '  return "false"\n'
                'end tell'
            )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        if "true" in (result.stdout or "").lower():
            return "窗口已居中"
        return "窗口居中失败"
    except Exception as e:
        return f"窗口居中失败: {e}"


def _center_window_win(title: str) -> str:
    if not _HAS_WIN32:
        return "需要安装 pywin32: pip install pywin32"
    try:
        import win32gui
        import win32api
        import win32con

        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        if title:
            hwnd = win32gui.FindWindow(None, title)
            if not hwnd:
                return f"未找到窗口: {title}"
        else:
            hwnd = win32gui.GetForegroundWindow()

        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        win32gui.MoveWindow(hwnd, x, y, w, h, True)
        return "窗口已居中"
    except Exception as e:
        return f"窗口居中失败: {e}"