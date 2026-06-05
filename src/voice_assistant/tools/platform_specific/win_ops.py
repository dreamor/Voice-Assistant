"""
Windows 平台特定工具 - win_ops
PowerShell 实现的系统操作
"""
import logging
import subprocess

from voice_assistant.security.safe_guard import SecurityLevel
from voice_assistant.tools.registry import ToolDefinition

logger = logging.getLogger(__name__)

_BLOCKED_PS_COMMANDS = frozenset([
    "Remove-Item", "rm ", "del ", "Format-", "Stop-Computer",
    "Restart-Computer", "Remove-WindowsFeature", "net user", "net localgroup",
])


def set_system_volume(level: int) -> str:
    """设置系统音量 (0-100)"""
    level = max(0, min(100, level))
    try:
        ps_cmd = (
            f"$wshShell = New-Object -ComObject WScript.Shell; "
            f"1..50 | ForEach-Object {{$wshShell.SendKeys([char]174)}}; "
            f"1..{level // 2} | ForEach-Object {{$wshShell.SendKeys([char]175)}}"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"音量已设置为 {level}%"
        return f"设置音量失败: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "设置音量超时"
    except (FileNotFoundError, OSError) as e:
        return f"设置音量失败: {e}"


def toggle_dark_mode() -> str:
    """切换深色/浅色模式"""
    try:
        ps_cmd = (
            "Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
            "Themes\\Personalize' -Name AppsUseLightTheme | Select-Object -ExpandProperty AppsUseLightTheme"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        is_light = "1" in result.stdout
        new_value = 0 if is_light else 1
        ps_cmd_set = (
            f"Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
            f"Themes\\Personalize' -Name AppsUseLightTheme -Value {new_value}; "
            f"Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\"
            f"Themes\\Personalize' -Name SystemUsesLightTheme -Value {new_value}"
        )
        subprocess.run(
            ["powershell", "-Command", ps_cmd_set],
            capture_output=True, text=True, timeout=10
        )
        return f"已切换为{'深色' if is_light else '浅色'}模式"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"切换深色模式失败: {e}"


def set_wallpaper(path: str) -> str:
    """设置桌面壁纸"""
    try:
        ps_cmd = (
            "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
            "public class Wallpaper{[DllImport(\"user32.dll\",CharSet=CharSet.Auto)]"
            "public static extern int SystemParametersInfo(int uAction,int uParam,string lpvParam,int fuWinIni);}';"
            f"[Wallpaper]::SystemParametersInfo(0x0014,0,'{path}',0x01 -bor 0x02)"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"壁纸已设置: {path}"
        return f"设置壁纸失败: {result.stderr}"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"设置壁纸失败: {e}"


def lock_screen() -> str:
    """锁定屏幕"""
    try:
        subprocess.run(
            ["powershell", "-Command",
             "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
             "public class Lock{[DllImport(\"user32.dll\")]public static extern bool LockWorkStation();}';"
             "[Lock]::LockWorkStation()"],
            capture_output=True, text=True, timeout=5
        )
        return "已锁定屏幕"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"锁定屏幕失败: {e}"


def get_battery() -> str:
    """获取电池信息"""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return "未检测到电池"
        status = "充电中" if battery.power_plugged else "使用电池"
        remaining = ""
        if not battery.power_plugged and battery.secs_left > 0:
            hours, remainder = divmod(battery.secs_left, 3600)
            minutes = remainder // 60
            remaining = f"，剩余 {int(hours)}小时{int(minutes)}分钟"
        return f"电池: {battery.percent}% ({status}{remaining})"
    except ImportError:
        return "需要安装 psutil: pip install psutil"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"获取电池信息失败: {e}"


def show_notification(title: str, message: str) -> str:
    """显示系统通知"""
    try:
        ps_cmd = (
            "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
            "$notify = New-Object System.Windows.Forms.NotifyIcon;"
            "$notify.Icon = [System.Drawing.SystemIcons]::Information;"
            "$notify.Visible = $true;"
            f"$notify.ShowBalloonTip(5000, '{title}', '{message}', 'Info')"
        )
        subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10
        )
        return f"通知已发送: {title}"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return f"发送通知失败: {e}"


def set_display_mode(mode: str) -> str:
    """设置显示模式 (internal/external/extend/mirror)"""
    mode_map = {
        "internal": "/internal",
        "external": "/external",
        "extend": "/extend",
        "mirror": "/clone",
    }
    arg = mode_map.get(mode.lower())
    if not arg:
        return f"未知显示模式: {mode}，支持: internal, external, extend, mirror"
    try:
        subprocess.run(
            ["displayswitch.exe", arg],
            capture_output=True, text=True, timeout=10
        )
        return f"显示模式已设置为: {mode}"
    except FileNotFoundError:
        return "displayswitch.exe 不可用"
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"设置显示模式失败: {e}"


def toggle_bluetooth() -> str:
    """切换蓝牙开关 - 通过 Disable/Enable 蓝牙设备类的所有设备实现"""
    try:
        # 检测蓝牙设备的状态：取第一个状态为 OK / Error 的判定
        ps_query = (
            "Get-PnpDevice -Class Bluetooth | "
            "Where-Object { $_.Status -in 'OK','Error' } | "
            "Select-Object -First 1 -ExpandProperty Status"
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_query],
            capture_output=True, text=True, timeout=10,
        )
        status = (result.stdout or "").strip()
        is_on = status.upper() == "OK"
        action = "Disable-PnpDevice" if is_on else "Enable-PnpDevice"
        ps_toggle = (
            f"Get-PnpDevice -Class Bluetooth | "
            f"ForEach-Object {{ {action} -InstanceId $_.InstanceId -Confirm:$false }}"
        )
        toggle = subprocess.run(
            ["powershell", "-Command", ps_toggle],
            capture_output=True, text=True, timeout=15,
        )
        if toggle.returncode != 0:
            return f"切换蓝牙失败: {toggle.stderr.strip() or '需要管理员权限'}"
        return f"蓝牙已{'关闭' if is_on else '打开'}"
    except subprocess.TimeoutExpired:
        return "切换蓝牙超时"
    except (FileNotFoundError, OSError) as e:
        return f"切换蓝牙失败: {e}"


def toggle_wifi() -> str:
    """切换 Wi-Fi 开关 - 通过 netsh 启用/禁用 Wi-Fi 接口"""
    try:
        query = subprocess.run(
            ["netsh", "interface", "show", "interface", "name=Wi-Fi"],
            capture_output=True, text=True, timeout=10,
        )
        out = query.stdout or ""
        is_enabled = "Enabled" in out or "已启用" in out
        new_state = "disabled" if is_enabled else "enabled"
        result = subprocess.run(
            ["netsh", "interface", "set", "interface", "name=Wi-Fi", f"admin={new_state}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return f"切换 Wi-Fi 失败: {result.stderr.strip() or '需要管理员权限'}"
        return f"Wi-Fi 已{'关闭' if is_enabled else '打开'}"
    except FileNotFoundError:
        return "netsh.exe 不可用"
    except subprocess.TimeoutExpired:
        return "切换 Wi-Fi 超时"
    except OSError as e:
        return f"切换 Wi-Fi 失败: {e}"


def empty_trash() -> str:
    """清空回收站"""
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return f"清空回收站失败: {result.stderr.strip() or '未知错误'}"
        return "回收站已清空"
    except subprocess.TimeoutExpired:
        return "清空回收站超时"
    except (FileNotFoundError, OSError) as e:
        return f"清空回收站失败: {e}"


_APP_NAME_BLOCKED_CHARS = ("&", "|", "<", ">", "^", "`", "\"", "'", "\n", "\r")

# 常见应用友好名 -> 可执行名/UWP 启动 ID 映射
# 解决 LLM 用"Calculator"/"计算器"等友好名称时，os.startfile 找不到的问题
_APP_NAME_ALIASES = {
    # Windows 内置
    "calculator": "calc.exe",
    "计算器": "calc.exe",
    "notepad": "notepad.exe",
    "记事本": "notepad.exe",
    "paint": "mspaint.exe",
    "画图": "mspaint.exe",
    "snippingtool": "snippingtool.exe",
    "截图工具": "snippingtool.exe",
    "snip": "snippingtool.exe",
    "截图": "snippingtool.exe",
    "taskmgr": "taskmgr.exe",
    "任务管理器": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "control": "control.exe",
    "控制面板": "control.exe",
    "settings": "ms-settings:",
    "设置": "ms-settings:",
    "explorer": "explorer.exe",
    "文件资源管理器": "explorer.exe",
    "file explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "终端": "wt.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    # 微软全家桶
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpoint.exe",
    "ppt": "powerpoint.exe",
    "outlook": "outlook.exe",
    "邮件": "outlook.exe",
    "edge": "msedge.exe",
    "浏览器": "msedge.exe",
    "browser": "msedge.exe",
    # 第三方常用
    "chrome": "chrome.exe",
    "谷歌浏览器": "chrome.exe",
    "firefox": "firefox.exe",
    "火狐": "firefox.exe",
    "vscode": "code.exe",
    "vs code": "code.exe",
    "代码": "code.exe",
    "wechat": "WeChat.exe",
    "微信": "WeChat.exe",
    "qq": "QQ.exe",
    "telegram": "Telegram.exe",
    "spotify": "Spotify.exe",
}


def launch_application(app_name: str) -> str:
    """启动应用程序（按可执行名、Start Menu 名、UWP 友好名或路径）"""
    logger.info(f"[LAUNCH] enter launch_application app_name={app_name!r} pid={__import__('os').getpid()}")
    if not app_name or not app_name.strip():
        return "应用名称不能为空"
    app_name = app_name.strip()
    if any(c in app_name for c in _APP_NAME_BLOCKED_CHARS):
        return "应用名包含非法字符"

    target = _APP_NAME_ALIASES.get(app_name.lower(), app_name)
    logger.info(f"[LAUNCH] resolved target={target!r} (from alias? {target != app_name})")
    if target != app_name and not target.endswith(":"):
        return _launch_by_path_or_start(target, app_name)

    return _launch_by_path_or_start(target, app_name)


def _launch_by_path_or_start(target: str, display_name: str) -> str:
    """先按文件路径启动，再搜索 Start Menu，最后用 cmd /c start 兜底"""
    import os
    import subprocess as sp

    logger.info(f"[LAUNCH] _launch_by_path_or_start target={target!r} display={display_name!r}")
    try:
        # 1) 绝对路径且文件存在 -> os.startfile
        if os.path.isabs(target) and os.path.exists(target):
            logger.info(f"[LAUNCH] branch=1 os.startfile(absolute path)")
            os.startfile(target)  # type: ignore[attr-defined]
            return f"已启动: {display_name}"

        # 2) 相对路径存在 -> 也直接启动
        if os.path.exists(target):
            logger.info(f"[LAUNCH] branch=2 os.startfile(relative path)")
            os.startfile(target)  # type: ignore[attr-defined]
            return f"已启动: {display_name}"

        # 3) 尝试补 .exe 后缀（PATH 中的可执行名）
        if not target.lower().endswith(".exe") and not target.endswith(":"):
            exe = target + ".exe"
            if os.path.exists(exe):
                logger.info(f"[LAUNCH] branch=3 os.startfile({exe})")
                os.startfile(exe)  # type: ignore[attr-defined]
                return f"已启动: {display_name}"

        # 4) 协议/URI 启动（ms-settings: 等）
        if target.endswith(":"):
            sp.Popen(
                ["cmd", "/c", "start", "", target],
                creationflags=getattr(sp, "CREATE_NO_WINDOW", 0),
            )
            return f"已启动: {display_name}"

        # 5) 搜索 Get-StartApps 匹配 UWP/开始菜单应用
        safe_name = target.replace("'", "''")
        try:
            ps_cmd = (
                "$apps = Get-StartApps | Where-Object { $_.Name -like '*"
                + safe_name + "*' }; "
                "if ($apps) { Start-Process ($apps[0].AppID); $apps[0].Name }"
            )
            result = sp.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"已启动应用: {result.stdout.strip()}"
        except (sp.TimeoutExpired, FileNotFoundError, OSError):
            pass

        # 6) 搜索 Start Menu .lnk 快捷方式
        try:
            ps_cmd = (
                "$lnk = Get-ChildItem -Path "
                "'$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs',"
                "'$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs' "
                "-Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue "
                "| Where-Object { $_.BaseName -like '*" + safe_name + "*' } "
                "| Select-Object -First 1; "
                "if ($lnk) { Start-Process $lnk.FullName; $lnk.BaseName }"
            )
            result = sp.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"已启动应用: {result.stdout.strip()}"
        except (sp.TimeoutExpired, FileNotFoundError, OSError):
            pass

        # 7) 尝试 where.exe 查找 PATH 中的可执行文件
        exe_name = target if target.lower().endswith(".exe") else target + ".exe"
        try:
            where_result = sp.run(
                ["where.exe", exe_name],
                capture_output=True, text=True, timeout=10,
            )
            if where_result.returncode == 0 and where_result.stdout.strip():
                exe_path = where_result.stdout.strip().split("\n")[0].strip()
                logger.info(f"[LAUNCH] branch=7 where.exe found {exe_path}, os.startfile")
                os.startfile(exe_path)  # type: ignore[attr-defined]
                return f"已启动: {display_name}"
            logger.info(f"[LAUNCH] branch=7 where.exe rc={where_result.returncode} out={where_result.stdout!r}")
        except (FileNotFoundError, OSError) as e:
            logger.info(f"[LAUNCH] branch=7 where.exe error {e}")

        # 8) 兜底：交给 Windows shell 解析（Start Menu、UWP、PATH 等）
        logger.info(f"[LAUNCH] branch=8 fallback cmd /c start '' {target}")
        result = sp.run(
            ["cmd", "/c", "start", "", target],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(sp, "CREATE_NO_WINDOW", 0),
        )
        logger.info(f"[LAUNCH] branch=8 rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}")
        if result.returncode == 0:
            return f"已启动: {display_name}"
        return f"启动失败: {result.stderr.strip() or '未知错误'}"
    except sp.TimeoutExpired:
        return f"启动超时: {display_name}"
    except FileNotFoundError:
        return f"未找到应用: {display_name}"
    except OSError as e:
        return f"启动失败: {e}"


def open_file(file_path: str) -> str:
    """用默认应用打开文件"""
    if not file_path or not file_path.strip():
        return "文件路径不能为空"
    try:
        import os
        os.startfile(file_path)  # type: ignore[attr-defined]
        return f"已打开: {file_path}"
    except FileNotFoundError:
        return f"文件不存在: {file_path}"
    except OSError as e:
        return f"打开失败: {e}"


def run_powershell_script(script: str) -> str:
    """执行 PowerShell 脚本（受限）"""
    for b in _BLOCKED_PS_COMMANDS:
        if b.lower() in script.lower():
            return f"不允许的操作: 包含被禁止的命令 '{b}'"
    try:
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip() if result.stdout else ""
        error = result.stderr.strip() if result.stderr else ""
        if result.returncode != 0:
            return f"执行失败 (exit {result.returncode}): {error or '未知错误'}"
        return output if output else "执行成功（无输出）"
    except subprocess.TimeoutExpired:
        return "脚本执行超时（30秒）"
    except (FileNotFoundError, OSError) as e:
        return f"执行失败: {e}"


def quit_application(app_name: str) -> str:
    """退出应用程序"""
    if not app_name or not app_name.strip():
        return "应用名称不能为空"
    try:
        result = subprocess.run(
            ["taskkill", "/IM", app_name.strip(), "/F"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"已退出应用: {app_name}"
        if "not found" in result.stderr.lower() or "未找到" in result.stderr:
            return f"应用未运行: {app_name}"
        return f"退出应用失败: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return f"退出应用超时: {app_name}"
    except (FileNotFoundError, OSError) as e:
        return f"退出应用失败: {e}"


def is_application_running(app_name: str) -> str:
    """检查应用是否正在运行"""
    if not app_name or not app_name.strip():
        return "应用名称不能为空"
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {app_name.strip()}"],
            capture_output=True, text=True, timeout=10
        )
        if app_name.strip().lower() in result.stdout.lower():
            return f"{app_name} 正在运行"
        return f"{app_name} 未运行"
    except subprocess.TimeoutExpired:
        return f"检查应用状态超时: {app_name}"
    except (FileNotFoundError, OSError) as e:
        return f"检查应用状态失败: {e}"


def get_win_tools() -> list[ToolDefinition]:
    """返回 Windows 平台特定工具"""
    return [
        ToolDefinition(
            name="set_system_volume",
            description="设置系统音量 (0-100)",
            parameters={
                "type": "object",
                "properties": {"level": {"type": "integer", "description": "音量级别 0-100"}},
                "required": ["level"],
            },
            handler=set_system_volume,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="toggle_dark_mode",
            description="切换深色/浅色模式",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=toggle_dark_mode,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="set_wallpaper",
            description="设置桌面壁纸",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "壁纸图片路径"}},
                "required": ["path"],
            },
            handler=set_wallpaper,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="lock_screen",
            description="锁定屏幕",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lock_screen,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="get_battery",
            description="获取电池信息",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=get_battery,
            security_level=SecurityLevel.READ_ONLY,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="show_notification",
            description="显示系统通知",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "通知标题"},
                    "message": {"type": "string", "description": "通知内容"},
                },
                "required": ["title", "message"],
            },
            handler=show_notification,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="toggle_bluetooth",
            description="切换蓝牙开关（需要管理员权限）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=toggle_bluetooth,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="toggle_wifi",
            description="切换 Wi-Fi 开关（需要管理员权限）",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=toggle_wifi,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="empty_trash",
            description="清空回收站",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=empty_trash,
            security_level=SecurityLevel.DANGEROUS,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="launch_application",
            description="启动应用程序（按可执行名、Start Menu 名或路径）",
            parameters={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "应用名称或路径"},
                },
                "required": ["app_name"],
            },
            handler=launch_application,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="open_file",
            description="用默认应用打开文件",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件绝对路径"},
                },
                "required": ["file_path"],
            },
            handler=open_file,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="set_display_mode",
            description="设置显示模式 (internal/external/extend/mirror)",
            parameters={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "显示模式: internal, external, extend, mirror",
                        "enum": ["internal", "external", "extend", "mirror"],
                    },
                },
                "required": ["mode"],
            },
            handler=set_display_mode,
            security_level=SecurityLevel.WRITE,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="run_powershell_script",
            description="执行 PowerShell 脚本（受限，禁止危险命令）",
            parameters={
                "type": "object",
                "properties": {"script": {"type": "string", "description": "PowerShell 脚本内容"}},
                "required": ["script"],
            },
            handler=run_powershell_script,
            security_level=SecurityLevel.DANGEROUS,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="quit_application",
            description="退出应用程序（强制结束进程）",
            parameters={
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "应用进程名，如 chrome.exe、notepad.exe"}},
                "required": ["app_name"],
            },
            handler=quit_application,
            security_level=SecurityLevel.DANGEROUS,
            platforms=["windows"],
        ),
        ToolDefinition(
            name="is_application_running",
            description="检查应用是否正在运行",
            parameters={
                "type": "object",
                "properties": {"app_name": {"type": "string", "description": "应用进程名，如 chrome.exe"}},
                "required": ["app_name"],
            },
            handler=is_application_running,
            security_level=SecurityLevel.READ_ONLY,
            platforms=["windows"],
        ),
    ]
