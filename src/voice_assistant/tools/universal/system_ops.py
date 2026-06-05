"""
通用系统信息工具 - system_ops
获取系统信息、进程列表、活跃窗口标题
"""
import logging
import os
import platform
import subprocess
import sys

logger = logging.getLogger(__name__)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_system_info() -> str:
    """获取系统信息"""
    lines = [
        f"操作系统: {platform.system()} {platform.release()}",
        f"架构: {platform.machine()}",
        f"处理器: {platform.processor() or '未知'}",
        f"Python 版本: {sys.version.split()[0]}",
        f"主机名: {platform.node()}",
        f"当前目录: {os.getcwd()}",
    ]
    if HAS_PSUTIL:
        lines.append(f"CPU 核心: {os.cpu_count()} 逻辑核心")
        mem = psutil.virtual_memory()
        lines.append(f"内存: {_format_size(mem.used)} / {_format_size(mem.total)} ({mem.percent}%)")
        disk = psutil.disk_usage('/')
        lines.append(f"磁盘: {_format_size(disk.used)} / {_format_size(disk.total)} ({disk.percent}%)")
        battery = psutil.sensors_battery()
        if battery:
            status = "充电中" if battery.power_plugged else "使用电池"
            lines.append(f"电池: {battery.percent}% ({status})")
    return '\n'.join(lines)


def get_running_processes(count: int = 20) -> str:
    """获取正在运行的进程列表（按 CPU 使用率排序）"""
    if not HAS_PSUTIL:
        return "需要安装 psutil: pip install psutil"
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = p.info
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
        procs = procs[:count]
        lines = [f"{'PID':>8} {'CPU%':>6} {'MEM%':>6}  名称"]
        lines.append('-' * 42)
        for p in procs:
            lines.append(
                f"{p['pid']:>8} {p.get('cpu_percent') or 0:>6.1f} "
                f"{p.get('memory_percent') or 0:>6.1f}  {p.get('name', '?')}"
            )
        return '\n'.join(lines)
    except Exception as e:
        return f"获取进程列表失败: {e}"


def get_active_window_title() -> str:
    """获取当前活跃窗口标题"""
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get title of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"当前活跃窗口: {result.stdout.strip()}"
            return "无法获取活跃窗口"
        elif system == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object -First 1).MainWindowTitle"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"当前活跃窗口: {result.stdout.strip()}"
            return "无法获取活跃窗口"
        else:
            return "仅支持 Mac 和 Windows"
    except subprocess.TimeoutExpired:
        return "获取窗口超时"
    except Exception as e:
        return f"获取窗口失败: {e}"


def kill_process(pid: int) -> str:
    """终止进程"""
    if not HAS_PSUTIL:
        return "需要安装 psutil: pip install psutil"
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        proc.wait(timeout=5)
        return f"已终止进程: {name} (PID: {pid})"
    except psutil.NoSuchProcess:
        return f"进程不存在: PID {pid}"
    except psutil.AccessDenied:
        return f"没有权限终止进程: PID {pid}"
    except psutil.TimeoutExpired:
        try:
            proc.kill()
            return f"已强制终止进程: {name} (PID: {pid})"
        except Exception as e:
            return f"终止进程失败: {e}"
    except Exception as e:
        return f"终止进程失败: {e}"


def _format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
