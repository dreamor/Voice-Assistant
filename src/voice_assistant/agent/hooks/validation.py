"""Validation Hook — 参数校验拦截"""
import logging

from voice_assistant.agent.hooks.chain import HookContext, HookResult
from voice_assistant.tools.registry import _validate_arguments

logger = logging.getLogger(__name__)


class ValidationHook:
    """将参数校验封装为 before hook"""

    def before(self, ctx: HookContext) -> HookResult:
        parameters = ctx.metadata.get("parameters")
        if not parameters:
            return HookResult()

        errors = _validate_arguments(parameters, ctx.arguments)
        if errors:
            msg = f"参数校验失败: {'; '.join(errors)}"
            return HookResult(
                proceed=False,
                reason=msg,
                modified_result={"success": False, "result": msg},
            )
        return HookResult()

    def after(self, ctx: HookContext) -> HookResult:
        return HookResult()
