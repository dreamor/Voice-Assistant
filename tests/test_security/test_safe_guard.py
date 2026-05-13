"""SafeGuard 单元测试"""
from voice_assistant.security.safe_guard import (
    GuardAction,
    SafeGuard,
    SecurityLevel,
    ToolPolicy,
)


class TestSecurityLevel:
    def test_values(self):
        assert SecurityLevel.READ_ONLY.value == "read_only"
        assert SecurityLevel.WRITE.value == "write"
        assert SecurityLevel.DANGEROUS.value == "dangerous"


class TestGuardAction:
    def test_values(self):
        assert GuardAction.APPROVED.value == "approved"
        assert GuardAction.CONFIRM_NEEDED.value == "confirm_needed"
        assert GuardAction.DOUBLE_CONFIRM.value == "double_confirm"
        assert GuardAction.BLOCKED.value == "blocked"


class TestSafeGuardCheck:
    def setup_method(self):
        self.guard = SafeGuard()

    def test_read_only_approved(self):
        result = self.guard.check("get_system_info", {}, SecurityLevel.READ_ONLY)
        assert result.action == GuardAction.APPROVED
        assert result.tool_name == "get_system_info"

    def test_write_needs_confirm(self):
        result = self.guard.check("write_file", {"path": "/tmp/test.txt"}, SecurityLevel.WRITE)
        assert result.action == GuardAction.CONFIRM_NEEDED
        assert "write_file" in result.message

    def test_dangerous_double_confirm(self):
        result = self.guard.check("delete_file", {"path": "/tmp/test.txt"}, SecurityLevel.DANGEROUS)
        assert result.action == GuardAction.DOUBLE_CONFIRM
        assert "危险" in result.message

    def test_blocked_tool(self):
        guard = SafeGuard(policies=[ToolPolicy(tool_name="rm_rf", blocked=True)])
        result = guard.check("rm_rf", {}, SecurityLevel.WRITE)
        assert result.action == GuardAction.BLOCKED
        assert "阻止" in result.message

    def test_block_and_unblock(self):
        self.guard.block_tool("test_tool")
        result = self.guard.check("test_tool", {}, SecurityLevel.READ_ONLY)
        assert result.action == GuardAction.BLOCKED

        self.guard.unblock_tool("test_tool")
        result = self.guard.check("test_tool", {}, SecurityLevel.READ_ONLY)
        assert result.action == GuardAction.APPROVED

    def test_override_level(self):
        guard = SafeGuard(policies=[
            ToolPolicy(tool_name="read_logs", override_level=SecurityLevel.DANGEROUS)
        ])
        result = guard.check("read_logs", {}, SecurityLevel.READ_ONLY)
        assert result.action == GuardAction.DOUBLE_CONFIRM

    def test_confirm_message_with_args(self):
        result = self.guard.check("write_file", {"path": "/tmp/test.txt", "content": "hello"}, SecurityLevel.WRITE)
        assert "path=" in result.message
        assert "content=" in result.message

    def test_confirm_message_long_arg_truncated(self):
        long_val = "x" * 100
        result = self.guard.check("write_file", {"content": long_val}, SecurityLevel.WRITE)
        assert "..." in result.message

    def test_dangerous_patterns_in_message(self):
        result = self.guard.check("delete_file", {"path": "/tmp/x"}, SecurityLevel.DANGEROUS)
        assert "删除文件" in result.message

    def test_unknown_tool_default_write(self):
        result = self.guard.check("custom_tool", {}, SecurityLevel.WRITE)
        assert result.action == GuardAction.CONFIRM_NEEDED
