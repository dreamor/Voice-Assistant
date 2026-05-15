"""
通用通知提醒工具 - notification_ops
设置定时提醒（延迟弹窗通知）
show_notification 已存在于平台 ops，此模块补充延迟提醒功能
"""
import logging
import platform
import subprocess
import threading

logger = logging.getLogger(__name__)


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _is_win() -> bool:
    return platform.system() == "Windows"


def _ps_escape(s: str) -> str:
    """转义 PowerShell 单引号字符串中的特殊字符"""
    return s.replace("'", "''").replace("\r", " ").replace("\n", " ")


def _send_delayed_notification_mac(title: str, message: str, seconds: int) -> None:
    """Mac 后台延迟发送通知"""
    import time
    time.sleep(seconds)
    try:
        escaped_title = title.replace('\\', '\\\\').replace('"', '\\"')
        escaped_message = message.replace('\\', '\\\\').replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{escaped_message}" with title "{escaped_title}"'],
            capture_output=True, text=True, timeout=5
        )
    except (subprocess.TimeoutExpired, OSError):
        logger.warning(f"延迟通知发送失败: {title}")


def _send_delayed_notification_win(title: str, message: str, seconds: int) -> None:
    """Windows 后台延迟发送通知"""
    import time
    time.sleep(seconds)
    try:
        safe_title = _ps_escape(title)
        safe_message = _ps_escape(message)
        ps_cmd = (
            "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
            "$notify = New-Object System.Windows.Forms.NotifyIcon;"
            "$notify.Icon = [System.Drawing.SystemIcons]::Information;"
            "$notify.Visible = $true;"
            f"$notify.ShowBalloonTip(5000, '{safe_title}', '{safe_message}', 'Info')"
        )
        subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
    except (subprocess.TimeoutExpired, OSError):
        logger.warning(f"延迟通知发送失败: {title}")


def set_reminder(title: str, message: str, seconds: int) -> str:
    """设置定时提醒（秒数+标题+消息），到时间后弹出系统通知"""
    if seconds <= 0:
        return "提醒时间必须大于 0 秒"
    if seconds > 86400:
        return "提醒时间不能超过 86400 秒（24 小时）"

    try:
        if _is_mac():
            t = threading.Thread(
                target=_send_delayed_notification_mac,
                args=(title, message, seconds),
                daemon=True,
            )
            t.start()
        elif _is_win():
            t = threading.Thread(
                target=_send_delayed_notification_win,
                args=(title, message, seconds),
                daemon=True,
            )
            t.start()
        else:
            return "当前平台不支持提醒功能"

        if seconds < 60:
            time_desc = f"{seconds} 秒"
        elif seconds < 3600:
            time_desc = f"{seconds // 60} 分钟"
        else:
            h, m = divmod(seconds, 3600)
            time_desc = f"{h} 小时 {m // 60} 分钟"
        return f"已设置提醒: {time_desc}后提醒「{title}」"
    except (OSError, RuntimeError) as e:
        return f"设置提醒失败: {e}"
