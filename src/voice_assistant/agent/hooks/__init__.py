"""Agent 工具执行 Hook 系统

提供 before/after 中间件管道，将 SafeGuard、速率限制、参数校验等
横切关注点从 ToolRegistry.execute() 中解耦。
"""
from voice_assistant.agent.hooks.chain import HookChain, HookContext, HookResult
from voice_assistant.agent.hooks.guard import SafeGuardHook
from voice_assistant.agent.hooks.rate_limit import RateLimitHook
from voice_assistant.agent.hooks.validation import ValidationHook
from voice_assistant.agent.hooks.audit import AuditLogHook
from voice_assistant.agent.hooks.metrics import MetricsHook

__all__ = [
    "HookChain",
    "HookContext",
    "HookResult",
    "SafeGuardHook",
    "RateLimitHook",
    "ValidationHook",
    "AuditLogHook",
    "MetricsHook",
]
