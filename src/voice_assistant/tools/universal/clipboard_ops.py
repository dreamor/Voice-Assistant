"""
通用剪贴板操作工具 - clipboard_ops
跨平台剪贴板读写
"""
import logging
import subprocess
import platform

logger = logging.getLogger(__name__)


def get_clipboard() -> str:
    """获取剪贴板内容"""
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True, text=True, timeout=5
            )
        elif system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5
            )
        else:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=5
            )
        if result.returncode == 0:
            content = result.stdout
            if len(content) > 2000:
                content = content[:2000] + f"\n... (共 {len(result.stdout)} 字符，仅显示前 2000)"
            return f"剪贴板内容:\n{content}" if content else "剪贴板为空"
        return f"获取剪贴板失败: {result.stderr}"
    except FileNotFoundError:
        if system == "Linux":
            return "Linux 需要安装 xclip: sudo apt install xclip"
        return f"不支持的平台: {system}"
    except subprocess.TimeoutExpired:
        return "获取剪贴板超时"
    except Exception as e:
        return f"获取剪贴板失败: {e}"


def set_clipboard(text: str) -> str:
    """设置剪贴板内容"""
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["pbcopy"],
                input=text, text=True, capture_output=True, timeout=5
            )
        elif system == "Windows":
            escaped = text.replace("'", "''")
            result = subprocess.run(
                ["powershell", "-Command", f"Set-Clipboard -Value '{escaped}'"],
                capture_output=True, text=True, timeout=5
            )
        else:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text, text=True, capture_output=True, timeout=5
            )
        if result.returncode == 0:
            preview = text[:50] + "..." if len(text) > 50 else text
            return f"已复制到剪贴板: {preview}"
        return f"设置剪贴板失败: {result.stderr}"
    except FileNotFoundError:
        if system == "Linux":
            return "Linux 需要安装 xclip: sudo apt install xclip"
        return f"不支持的平台: {system}"
    except subprocess.TimeoutExpired:
        return "设置剪贴板超时"
    except Exception as e:
        return f"设置剪贴板失败: {e}"