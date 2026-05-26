"""SafeGuard Hook — 安全检查拦截"""
import logging

from voice_assistant.agent.hooks.chain import HookContext, HookResult
from voice_assistant.security.safe_guard import GuardAction, SafeGuard, SecurityLevel

logger = logging.getLogger(__name__)


class SafeGuardHook:
    """将 SafeGuard 检查封装为 before hook"""

    def __init__(self, guard: SafeGuard) -> None:
        self._guard = guard

    def before(self, ctx: HookContext) -> HookResult:
        security_level = ctx.metadata.get("security_level", SecurityLevel.WRITE)
        guard_result = self._guard.check(ctx.tool_name, ctx.arguments, security_level)
        ctx.metadata["guard_result"] = guard_result

        if guard_result.action == GuardAction.BLOCKED:
            return HookResult(
                proceed=False,
                reason=f"操作被阻止: {guard_result.message}",
                modified_result={
                    "success": False,
                    "result": f"操作被阻止: {guard_result.message}",
                },
            )

        if guard_result.action in (GuardAction.CONFIRM_NEEDED, GuardAction.DOUBLE_CONFIRM):
            return HookResult(
                proceed=False,
                reason=guard_result.message,
                modified_result={
                    "success": True,
                    "result": guard_result.message,
                    "needs_confirmation": True,
                    "guard_result": guard_result,
                },
            )

        return HookResult()

    def after(self, ctx: HookContext) -> HookResult:
        return HookResult()
