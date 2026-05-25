"""每工具速率限制测试"""

from voice_assistant.security.validation import (
    TOOL_RATE_LIMITS,
    ToolRateLimiter,
    _get_tool_group,
)


class TestGetToolGroup:
    def test_file_ops_prefix(self):
        assert _get_tool_group("open_file") == "file_ops"
        assert _get_tool_group("read_file") == "file_ops"
        assert _get_tool_group("delete_file") == "file_ops"
        assert _get_tool_group("find_files") == "file_ops"

    def test_system_ops_prefix(self):
        assert _get_tool_group("launch_application") == "system_ops"
        assert _get_tool_group("kill_process") == "system_ops"
        assert _get_tool_group("get_running_processes") == "system_ops"
        assert _get_tool_group("screenshot") == "system_ops"

    def test_network_ops_prefix(self):
        assert _get_tool_group("web_search") == "network_ops"
        assert _get_tool_group("http_request") == "network_ops"

    def test_default_group(self):
        assert _get_tool_group("calculate") == "default"
        assert _get_tool_group("get_system_info") == "system_ops"  # get_system_ 前缀
        assert _get_tool_group("some_unknown_tool") == "default"


class TestToolRateLimiter:
    def test_allows_under_limit(self):
        limiter = ToolRateLimiter(limits={"default": (3, 60.0)})
        for _ in range(3):
            allowed, msg = limiter.check("my_tool")
            assert allowed
            assert msg == ""

    def test_blocks_over_limit(self):
        limiter = ToolRateLimiter(limits={"default": (2, 60.0)})
        limiter.check("my_tool")
        limiter.check("my_tool")
        allowed, msg = limiter.check("my_tool")
        assert not allowed
        assert "过于频繁" in msg

    def test_separate_tools_separate_limits(self):
        limiter = ToolRateLimiter(limits={"default": (1, 60.0)})
        allowed1, _ = limiter.check("tool_a")
        allowed2, _ = limiter.check("tool_b")
        assert allowed1
        assert allowed2

    def test_per_tool_independent_counting(self):
        """每个工具独立计数，同组工具互不影响。"""
        limiter = ToolRateLimiter(limits={"file_ops": (2, 60.0)})
        # open_file 和 read_file 都在 file_ops 组，但各自独立计数
        limiter.check("open_file")
        limiter.check("read_file")
        # 各自只用了 1 次，都还能再调
        allowed_a, _ = limiter.check("open_file")
        allowed_b, _ = limiter.check("read_file")
        assert allowed_a
        assert allowed_b
        # open_file 已用 2 次，第 3 次被限
        allowed, msg = limiter.check("open_file")
        assert not allowed

    def test_reset_specific_tool(self):
        limiter = ToolRateLimiter(limits={"default": (1, 60.0)})
        limiter.check("my_tool")
        allowed, _ = limiter.check("my_tool")
        assert not allowed
        limiter.reset("my_tool")
        allowed, _ = limiter.check("my_tool")
        assert allowed

    def test_reset_all(self):
        limiter = ToolRateLimiter(limits={"default": (1, 60.0)})
        limiter.check("tool_a")
        limiter.check("tool_b")
        limiter.reset()
        allowed_a, _ = limiter.check("tool_a")
        allowed_b, _ = limiter.check("tool_b")
        assert allowed_a
        assert allowed_b

    def test_default_limits_valid(self):
        """确保默认配置中的所有限制都是正数。"""
        for group, (calls, period) in TOOL_RATE_LIMITS.items():
            assert calls > 0, f"分组 {group} 的调用次数必须 > 0"
            assert period > 0, f"分组 {group} 的时间窗口必须 > 0"
