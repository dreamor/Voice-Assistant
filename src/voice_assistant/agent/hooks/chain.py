"""Hook 链 — 工具执行的中间件管道"""
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class HookContext:
    """hook 上下文，可被修改"""

    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    """hook 返回值"""

    proceed: bool = True
    reason: str | None = None
    modified_args: dict[str, Any] | None = None
    modified_result: dict[str, Any] | None = None


class ToolHook(Protocol):
    """工具执行 hook 协议"""

    def before(self, ctx: HookContext) -> HookResult:
        """执行前拦截。返回 HookResult(proceed=False) 阻止执行。"""
        ...

    def after(self, ctx: HookContext) -> HookResult:
        """执行后拦截。可修改 result。"""
        ...


class HookChain:
    """hook 链，按注册顺序执行 before/after"""

    def __init__(self) -> None:
        self._hooks: list[ToolHook] = []

    def add(self, hook: ToolHook) -> None:
        self._hooks.append(hook)

    def run_before(self, ctx: HookContext) -> HookResult:
        """执行所有 before hook。任一 hook 返回 proceed=False 即停止。"""
        for hook in self._hooks:
            try:
                result = hook.before(ctx)
                if result.modified_args is not None:
                    ctx.arguments = result.modified_args
                if not result.proceed:
                    logger.info(f"[HookChain] before hook 阻止执行: {result.reason}")
                    return result
            except Exception as e:
                logger.error(f"[HookChain] before hook 异常: {e}", exc_info=True)
        return HookResult()

    def run_after(self, ctx: HookContext) -> HookResult:
        """执行所有 after hook。可修改 result。"""
        for hook in self._hooks:
            try:
                result = hook.after(ctx)
                if result.modified_result is not None:
                    ctx.result = result.modified_result
            except Exception as e:
                logger.error(f"[HookChain] after hook 异常: {e}", exc_info=True)
        return HookResult()
