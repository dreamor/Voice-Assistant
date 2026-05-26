"""RateLimit Hook — 速率限制拦截"""
import logging

from voice_assistant.agent.hooks.chain import HookContext, HookResult
from voice_assistant.security.validation import tool_limiter

logger = logging.getLogger(__name__)


class RateLimitHook:
    """将 tool_limiter 检查封装为 before hook"""

    def before(self, ctx: HookContext) -> HookResult:
        allowed, msg = tool_limiter.check(ctx.tool_name)
        if not allowed:
            return HookResult(
                proceed=False,
                reason=msg,
                modified_result={"success": False, "result": msg},
            )
        return HookResult()

    def after(self, ctx: HookContext) -> HookResult:
        return HookResult()
