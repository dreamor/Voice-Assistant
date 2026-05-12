"""
安全守卫 - Agent tool 执行安全控制
对 tool 调用进行分级拦截和确认
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class SecurityLevel(Enum):
    READ_ONLY = "read_only"   # 只读操作，自动执行
    WRITE = "write"           # 写操作，需单次确认
    DANGEROUS = "dangerous"   # 危险操作，需二次确认


class GuardAction(Enum):
    APPROVED = "approved"            # 直接执行
    CONFIRM_NEEDED = "confirm_needed"     # 需要单次确认
    DOUBLE_CONFIRM = "double_confirm"     # 需要二次确认
    BLOCKED = "blocked"              # 被阻止


@dataclass
class GuardResult:
    action: GuardAction
    tool_name: str
    arguments: dict
    message: str = ""
    reason: str = ""


@dataclass
class ToolPolicy:
    """单个 tool 的安全策略覆盖"""
    tool_name: str
    override_level: Optional[SecurityLevel] = None
    require_confirmation: Optional[bool] = None
    blocked: bool = False
    note: str = ""


class SafeGuard:
    """安全守卫，管理 tool 执行的安全分级"""

    DANGEROUS_PATTERNS = {
        "delete_file": "删除文件",
        "delete_directory": "删除目录",
        "kill_process": "终止进程",
        "shutdown": "关机",
        "restart": "重启",
        "force_quit": "强制退出应用",
        "empty_trash": "清空回收站",
    }

    def __init__(self, policies: list[ToolPolicy] = None):
        self._policies: dict[str, ToolPolicy] = {}
        self._blocked: set[str] = set()
        for p in (policies or []):
            self._policies[p.tool_name] = p
            if p.blocked:
                self._blocked.add(p.tool_name)

    def block_tool(self, tool_name: str):
        self._blocked.add(tool_name)

    def unblock_tool(self, tool_name: str):
        self._blocked.discard(tool_name)

    def check(self, tool_name: str, arguments: dict,
              default_level: SecurityLevel = SecurityLevel.WRITE) -> GuardResult:
        """检查 tool 调用是否需要确认

        Args:
            tool_name: 工具名
            arguments: 调用参数
            default_level: tool 注册时的默认安全等级

        Returns:
            GuardResult 包含执行策略
        """
        # 1. 阻止列表检查
        if tool_name in self._blocked:
            return GuardResult(
                action=GuardAction.BLOCKED,
                tool_name=tool_name,
                arguments=arguments,
                message=f"操作已被安全策略阻止: {tool_name}",
                reason="blocked"
            )

        # 2. 检查自定义策略
        policy = self._policies.get(tool_name)
        effective_level = default_level
        if policy and policy.override_level:
            effective_level = policy.override_level

        # 3. 按等级决定
        if effective_level == SecurityLevel.READ_ONLY:
            return GuardResult(
                action=GuardAction.APPROVED,
                tool_name=tool_name,
                arguments=arguments
            )

        elif effective_level == SecurityLevel.WRITE:
            msg = self._build_confirm_message(tool_name, arguments)
            return GuardResult(
                action=GuardAction.CONFIRM_NEEDED,
                tool_name=tool_name,
                arguments=arguments,
                message=msg
            )

        elif effective_level == SecurityLevel.DANGEROUS:
            msg = self._build_confirm_message(tool_name, arguments)
            return GuardResult(
                action=GuardAction.DOUBLE_CONFIRM,
                tool_name=tool_name,
                arguments=arguments,
                message=f"⚠️ 危险操作: {msg}"
            )

        return GuardResult(
            action=GuardAction.BLOCKED,
            tool_name=tool_name,
            arguments=arguments
        )

    def _build_confirm_message(self, tool_name: str, arguments: dict) -> str:
        """构建用户可读的确认提示"""
        chinese_name = self.DANGEROUS_PATTERNS.get(tool_name, tool_name)

        # 格式化参数
        arg_strs = []
        for k, v in arguments.items():
            if isinstance(v, str) and len(v) > 50:
                v = v[:47] + "..."
            arg_strs.append(f"{k}={v}")

        if arg_strs:
            return f"即将执行: {chinese_name}({', '.join(arg_strs)})"
        return f"即将执行: {chinese_name}"