"""
跨平台适配层 - 统一 Mac/Windows 系统操作接口
"""
import logging
import platform
import subprocess
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class PlatformAdapter(ABC):
    """平台适配器抽象基类"""

    @abstractmethod
    def open_file(self, path: str) -> str:
        """用默认应用打开文件"""
        ...

    @abstractmethod
    def reveal_in_finder(self, path: str) -> str:
        """在文件管理器中显示文件"""
        ...

    @abstractmethod
    def get_default_app_for_extension(self, ext: str) -> str:
        """获取处理指定扩展名的默认应用"""
        ...

    @abstractmethod
    def open_url(self, url: str, browser: str = None) -> str:
        """在浏览器中打开 URL"""
        ...

    @abstractmethod
    def run_script(self, script: str, shell: str = None) -> tuple[int, str, str]:
        """执行系统脚本"""
        ...


class MacAdapter(PlatformAdapter):
    """macOS 适配器"""

    def open_file(self, path: str) -> str:
        result = subprocess.run(
            ["open", path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return f"打开失败: {result.stderr}"
        return "已打开"

    def reveal_in_finder(self, path: str) -> str:
        subprocess.run(
            ["open", "-R", path],
            capture_output=True, timeout=15
        )
        return "已在 Finder 中显示"

    def get_default_app_for_extension(self, ext: str) -> str:
        """通过 LaunchServices 获取默认应用"""
        if not ext.startswith("."):
            ext = f".{ext}"
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 f'tell application "System Events" to get name of '
                 f'(first application whose its default opens file type is "{ext[1:]}")'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            logger.debug(f"[MacAdapter] 获取扩展名 {ext} 的默认应用失败")
        return "未知应用"

    def open_url(self, url: str, browser: str = None) -> str:
        if browser:
            result = subprocess.run(
                ["open", "-a", browser, url],
                capture_output=True, text=True, timeout=30
            )
        else:
            result = subprocess.run(
                ["open", url],
                capture_output=True, text=True, timeout=30
            )
        if result.returncode != 0:
            return f"打开失败: {result.stderr}"
        return f"已在{' ' + browser if browser else ''}中打开"

    def run_script(self, script: str, shell: str = None) -> tuple[int, str, str]:
        """执行 AppleScript 或 shell 脚本"""
        if shell == "zsh" or shell == "bash":
            result = subprocess.run(
                [shell, "-c", script],
                capture_output=True, text=True, timeout=60
            )
        else:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=60
            )
        return result.returncode, result.stdout, result.stderr


class WindowsAdapter(PlatformAdapter):
    """Windows 适配器"""

    def open_file(self, path: str) -> str:
        import os
        expanded = os.path.expanduser(path)
        if not os.path.exists(expanded):
            return f"文件不存在: {path}"
        try:
            os.startfile(expanded)  # type: ignore[attr-defined]
            return "已打开"
        except OSError as e:
            return f"打开失败: {e}"

    def reveal_in_finder(self, path: str) -> str:
        subprocess.run(
            ["explorer", "/select,", path],
            capture_output=True, timeout=15
        )
        return "已在资源管理器中显示"

    def get_default_app_for_extension(self, ext: str) -> str:
        if not ext.startswith("."):
            ext = f".{ext}"
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 f"(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{ext}\\UserChoice').Progid"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            logger.debug(f"[WindowsAdapter] 获取扩展名 {ext} 的默认应用失败")
        return "未知应用"

    def open_url(self, url: str, browser: str = None) -> str:
        import webbrowser
        try:
            if browser:
                webbrowser.get(browser).open(url)
            else:
                webbrowser.open(url)
            return f"已在{' ' + browser if browser else ''}中打开"
        except webbrowser.Error as e:
            return f"打开失败: {e}"

    def run_script(self, script: str, shell: str = None) -> tuple[int, str, str]:
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True, text=True, timeout=60
        )
        return result.returncode, result.stdout, result.stderr


def detect_platform() -> str:
    """检测当前平台"""
    system = platform.system()
    if system == "Darwin":
        return "mac"
    elif system == "Windows":
        return "windows"
    else:
        return "linux"


def create_adapter() -> PlatformAdapter:
    """创建当前平台的适配器"""
    system = platform.system()
    if system == "Darwin":
        return MacAdapter()
    elif system == "Windows":
        return WindowsAdapter()
    else:
        raise RuntimeError(f"不支持的平台: {system}")


_current_platform = detect_platform()
_current_adapter: PlatformAdapter = None


def get_adapter() -> PlatformAdapter:
    """获取当前平台适配器（单例）"""
    global _current_adapter
    if _current_adapter is None:
        _current_adapter = create_adapter()
    return _current_adapter


def get_platform() -> str:
    return _current_platform
