"""AuditLog Hook — 审计日志（after hook）"""
import logging
import time

from voice_assistant.agent.hooks.chain import HookContext, HookResult

logger = logging.getLogger(__name__)


class AuditLogHook:
    """记录工具调用的审计日志"""

    def __init__(self, logger_: logging.Logger | None = None) -> None:
        self._log = logger_ or logger

    def before(self, ctx: HookContext) -> HookResult:
        ctx.metadata["audit_start"] = time.monotonic()
        return HookResult()

    def after(self, ctx: HookContext) -> HookResult:
        start = ctx.metadata.get("audit_start")
        duration_ms = int((time.monotonic() - start) * 1000) if start else -1
        success = ctx.result.get("success", False) if ctx.result else False
        output_preview = ""
        if ctx.result and ctx.result.get("result"):
            output_preview = str(ctx.result["result"])[:100]

        self._log.info(
            f"[Audit] tool={ctx.tool_name} success={success} "
            f"duration={duration_ms}ms args={ctx.arguments} "
            f"result={output_preview}"
        )
        return HookResult()
