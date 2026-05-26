"""Hook 链系统测试"""
from unittest.mock import MagicMock

from voice_assistant.agent.hooks.chain import HookChain, HookContext, HookResult
from voice_assistant.agent.hooks.guard import SafeGuardHook
from voice_assistant.agent.hooks.metrics import MetricsHook
from voice_assistant.agent.hooks.rate_limit import RateLimitHook
from voice_assistant.agent.hooks.validation import ValidationHook
from voice_assistant.security.safe_guard import GuardAction, GuardResult, SafeGuard, SecurityLevel


class TestHookChain:
    def test_before_hook_proceed(self):
        """before hook 返回 proceed=True 时继续执行"""
        chain = HookChain()

        class AllowHook:
            def before(self, ctx):
                return HookResult(proceed=True)

            def after(self, ctx):
                return HookResult()

        chain.add(AllowHook())
        ctx = HookContext(tool_name="test", arguments={})
        result = chain.run_before(ctx)
        assert result.proceed is True

    def test_before_hook_blocks(self):
        """before hook 返回 proceed=False 时阻止执行"""
        chain = HookChain()

        class BlockHook:
            def before(self, ctx):
                return HookResult(proceed=False, reason="blocked", modified_result={"success": False, "result": "blocked"})

            def after(self, ctx):
                return HookResult()

        chain.add(BlockHook())
        ctx = HookContext(tool_name="test", arguments={})
        result = chain.run_before(ctx)
        assert result.proceed is False
        assert result.reason == "blocked"

    def test_before_hook_modifies_args(self):
        """before hook 可修改参数"""
        chain = HookChain()

        class ModifyHook:
            def before(self, ctx):
                return HookResult(proceed=True, modified_args={"path": "/modified"})

            def after(self, ctx):
                return HookResult()

        chain.add(ModifyHook())
        ctx = HookContext(tool_name="test", arguments={"path": "/original"})
        chain.run_before(ctx)
        assert ctx.arguments == {"path": "/modified"}

    def test_after_hook_modifies_result(self):
        """after hook 可修改结果"""
        chain = HookChain()

        class ModifyResultHook:
            def before(self, ctx):
                return HookResult()

            def after(self, ctx):
                return HookResult(modified_result={"success": True, "result": "modified"})

        chain.add(ModifyResultHook())
        ctx = HookContext(tool_name="test", arguments={}, result={"success": True, "result": "original"})
        chain.run_after(ctx)
        assert ctx.result == {"success": True, "result": "modified"}

    def test_multiple_hooks_order(self):
        """多个 hook 按注册顺序执行"""
        chain = HookChain()
        order = []

        class OrderHook:
            def __init__(self, name):
                self.name = name

            def before(self, ctx):
                order.append(f"before_{self.name}")
                return HookResult()

            def after(self, ctx):
                order.append(f"after_{self.name}")
                return HookResult()

        chain.add(OrderHook("first"))
        chain.add(OrderHook("second"))
        ctx = HookContext(tool_name="test", arguments={})
        chain.run_before(ctx)
        chain.run_after(ctx)
        assert order == ["before_first", "before_second", "after_first", "after_second"]

    def test_before_hook_exception_handled(self):
        """before hook 异常不中断链"""
        chain = HookChain()

        class FailingHook:
            def before(self, ctx):
                raise RuntimeError("hook error")

            def after(self, ctx):
                return HookResult()

        class PassHook:
            def before(self, ctx):
                return HookResult(proceed=True)

            def after(self, ctx):
                return HookResult()

        chain.add(FailingHook())
        chain.add(PassHook())
        ctx = HookContext(tool_name="test", arguments={})
        result = chain.run_before(ctx)
        assert result.proceed is True


class TestSafeGuardHook:
    def test_allows_read_only(self):
        """READ_ONLY 工具自动放行"""
        guard = SafeGuard()
        hook = SafeGuardHook(guard)
        ctx = HookContext(
            tool_name="read_tool",
            arguments={},
            metadata={"security_level": SecurityLevel.READ_ONLY},
        )
        result = hook.before(ctx)
        assert result.proceed is True

    def test_blocks_dangerous(self):
        """BLOCKED 操作被阻止"""
        guard = MagicMock()
        guard.check.return_value = GuardResult(
            action=GuardAction.BLOCKED,
            tool_name="rm_rf",
            arguments={},
            message="危险操作",
        )
        hook = SafeGuardHook(guard)
        ctx = HookContext(
            tool_name="rm_rf",
            arguments={},
            metadata={"security_level": SecurityLevel.DANGEROUS},
        )
        result = hook.before(ctx)
        assert result.proceed is False
        assert "阻止" in result.reason

    def test_needs_confirmation(self):
        """需要确认的操作返回 needs_confirmation"""
        guard = MagicMock()
        guard.check.return_value = GuardResult(
            action=GuardAction.CONFIRM_NEEDED,
            tool_name="delete_file",
            arguments={},
            message="确认删除？",
        )
        hook = SafeGuardHook(guard)
        ctx = HookContext(
            tool_name="delete_file",
            arguments={},
            metadata={"security_level": SecurityLevel.WRITE},
        )
        result = hook.before(ctx)
        assert result.proceed is False
        assert result.modified_result["needs_confirmation"] is True


class TestRateLimitHook:
    def test_allows_under_limit(self):
        """速率限制内放行"""
        hook = RateLimitHook()
        ctx = HookContext(tool_name="test_tool", arguments={})
        result = hook.before(ctx)
        assert result.proceed is True


class TestValidationHook:
    def test_passes_valid_args(self):
        """参数校验通过"""
        hook = ValidationHook()
        ctx = HookContext(
            tool_name="test",
            arguments={"name": "hello"},
            metadata={"parameters": {"required": ["name"], "properties": {"name": {"type": "string"}}}},
        )
        result = hook.before(ctx)
        assert result.proceed is True

    def test_blocks_missing_required(self):
        """缺少必填参数被阻止"""
        hook = ValidationHook()
        ctx = HookContext(
            tool_name="test",
            arguments={},
            metadata={"parameters": {"required": ["name"], "properties": {"name": {"type": "string"}}}},
        )
        result = hook.before(ctx)
        assert result.proceed is False
        assert "缺少必填参数" in result.reason

    def test_skips_without_parameters(self):
        """无 parameters 元数据时跳过"""
        hook = ValidationHook()
        ctx = HookContext(tool_name="test", arguments={}, metadata={})
        result = hook.before(ctx)
        assert result.proceed is True


class TestMetricsHook:
    def test_collects_stats(self):
        """收集工具执行指标"""
        hook = MetricsHook()

        ctx1 = HookContext(tool_name="tool_a", arguments={})
        hook.before(ctx1)
        ctx1.result = {"success": True, "result": "ok"}
        hook.after(ctx1)

        ctx2 = HookContext(tool_name="tool_a", arguments={})
        hook.before(ctx2)
        ctx2.result = {"success": False, "result": "fail"}
        hook.after(ctx2)

        stats = hook.get_stats()
        assert "tool_a" in stats
        assert stats["tool_a"]["calls"] == 2
        assert stats["tool_a"]["success_rate"] == 0.5
