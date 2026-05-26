"""Metrics Hook — 执行耗时与成功率指标（after hook）"""
import logging
import time
from collections import defaultdict

from voice_assistant.agent.hooks.chain import HookContext, HookResult

logger = logging.getLogger(__name__)


class MetricsHook:
    """收集工具执行指标：调用次数、成功率、耗时分布"""

    def __init__(self) -> None:
        self._call_counts: dict[str, int] = defaultdict(int)
        self._success_counts: dict[str, int] = defaultdict(int)
        self._total_duration_ms: dict[str, float] = defaultdict(float)

    def before(self, ctx: HookContext) -> HookResult:
        ctx.metadata["metrics_start"] = time.monotonic()
        return HookResult()

    def after(self, ctx: HookContext) -> HookResult:
        start = ctx.metadata.get("metrics_start")
        duration_ms = (time.monotonic() - start) * 1000 if start else 0

        self._call_counts[ctx.tool_name] += 1
        self._total_duration_ms[ctx.tool_name] += duration_ms
        if ctx.result and ctx.result.get("success"):
            self._success_counts[ctx.tool_name] += 1

        return HookResult()

    def get_stats(self) -> dict[str, dict]:
        """获取所有工具的指标统计"""
        stats = {}
        for name, count in self._call_counts.items():
            avg_ms = self._total_duration_ms[name] / count if count else 0
            success_rate = self._success_counts[name] / count if count else 0
            stats[name] = {
                "calls": count,
                "success_rate": round(success_rate, 3),
                "avg_duration_ms": round(avg_ms, 1),
                "total_duration_ms": round(self._total_duration_ms[name], 1),
            }
        return stats
