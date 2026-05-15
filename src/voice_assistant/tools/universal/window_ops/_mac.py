"""窗口操作 - Mac 实现 (AppleScript via osascript)"""
import logging
import subprocess

logger = logging.getLogger(__name__)


def list_windows() -> str:
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
            lines = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
            if not lines:
                return "没有可见窗口"
            return "可见窗口列表:\n" + "\n".join(lines)
        return "获取窗口列表失败"
    except subprocess.TimeoutExpired:
        return "获取窗口列表超时"
    except (FileNotFoundError, OSError) as e:
        return f"获取窗口列表失败: {e}"


def focus_window(title: str) -> str:
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
    except (FileNotFoundError, OSError) as e:
        return f"聚焦窗口失败: {e}"


def minimize_window(title: str) -> str:
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
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"最小化窗口失败: {e}"


def maximize_window(title: str) -> str:
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
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"最大化窗口失败: {e}"


def close_window(title: str) -> str:
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
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"关闭窗口失败: {e}"


def resize_window(x: int, y: int, width: int, height: int, title: str) -> str:
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
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"调整窗口失败: {e}"


def center_window(title: str) -> str:
    try:
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
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"窗口居中失败: {e}"
