"""
通用网络操作工具 - network_ops
获取网络信息、WiFi 状态、ping 主机
"""
import logging
import platform
import re
import subprocess

logger = logging.getLogger(__name__)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

_HOST_RE = re.compile(r"^[A-Za-z0-9.\-:_]+$")


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _is_win() -> bool:
    return platform.system() == "Windows"


def get_network_info() -> str:
    """获取网络连接信息（IP、网关、DNS）"""
    if not HAS_PSUTIL:
        return "需要安装 psutil: pip install psutil"
    try:
        lines = []
        addrs = psutil.net_if_addrs()
        for iface, addr_list in addrs.items():
            ipv4 = [a.address for a in addr_list if a.family.name == "AF_INET"]
            if ipv4:
                lines.append(f"{iface}: {', '.join(ipv4)}")

        stats = psutil.net_if_stats()
        up_ifaces = [name for name, s in stats.items() if s.isup]
        if up_ifaces:
            lines.append(f"活跃接口: {', '.join(up_ifaces)}")

        try:
            gateways = psutil.net_connections(kind="inet")
            established = sum(1 for c in gateways if c.status == "ESTABLISHED")
            lines.append(f"已建立连接数: {established}")
        except (psutil.AccessDenied, PermissionError):
            pass

        return "网络信息:\n" + "\n".join(lines) if lines else "未检测到网络接口"
    except (psutil.Error, OSError) as e:
        return f"获取网络信息失败: {e}"


def get_wifi_status() -> str:
    """获取当前 WiFi 连接信息"""
    if _is_mac():
        try:
            result = subprocess.run(
                ["networksetup", "-getairportnetwork", "en0"],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout.strip()
            if "Current Wi-Fi Network" in output or "当前 Wi-Fi 网络" in output:
                return f"WiFi 已连接: {output}"
            if "You are not associated" in output or "未关联" in output:
                return "WiFi 未连接"
            return output
        except subprocess.TimeoutExpired:
            return "获取 WiFi 状态超时"
        except (FileNotFoundError, OSError) as e:
            return f"获取 WiFi 状态失败: {e}"
    elif _is_win():
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=10
            )
            lines = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                if any(k in line for k in ["SSID", "State", "Signal", "状态", "信号"]):
                    lines.append(line)
            if not lines:
                return "WiFi 未连接或不可用"
            return "WiFi 信息:\n" + "\n".join(lines)
        except subprocess.TimeoutExpired:
            return "获取 WiFi 状态超时"
        except (FileNotFoundError, OSError) as e:
            return f"获取 WiFi 状态失败: {e}"
    return "当前平台不支持 WiFi 状态查询"


def ping_host(host: str, count: int = 4) -> str:
    """ping 指定主机"""
    if not host or not host.strip():
        return "主机地址不能为空"
    host = host.strip()
    if not _HOST_RE.match(host) or len(host) > 253:
        return "主机地址包含非法字符"
    count = max(1, min(count, 10))
    try:
        if _is_win():
            cmd = ["ping", "-n", str(count), host]
        else:
            cmd = ["ping", "-c", str(count), "--", host]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=count * 5 + 5
        )
        output = result.stdout.strip()
        if not output:
            return f"ping {host} 失败"
        if len(output) > 2000:
            lines = output.split("\n")
            output = "\n".join(lines[:5] + ["..."] + lines[-3:])
        return output
    except subprocess.TimeoutExpired:
        return f"ping {host} 超时"
    except (FileNotFoundError, OSError) as e:
        return f"ping 失败: {e}"
