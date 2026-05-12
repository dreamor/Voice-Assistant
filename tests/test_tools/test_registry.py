"""ToolRegistry 单元测试"""
import pytest
from voice_assistant.tools.registry import ToolRegistry, ToolDefinition
from voice_assistant.security.safe_guard import SecurityLevel, SafeGuard, GuardAction


def _dummy_handler(**kwargs):
    return "ok"


def _error_handler(**kwargs):
    raise RuntimeError("boom")


class TestToolDefinition:
    def test_to_openai_function(self):
        td = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
            handler=_dummy_handler,
            security_level=SecurityLevel.READ_ONLY,
        )
        result = td.to_openai_function()
        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert result["function"]["description"] == "A test tool"
        assert "x" in result["function"]["parameters"]["properties"]

    def test_default_platforms(self):
        td = ToolDefinition(name="t", description="d", parameters={}, handler=_dummy_handler)
        assert "mac" in td.platforms
        assert "windows" in td.platforms


class TestToolRegistry:
    def setup_method(self):
        self.registry = ToolRegistry(current_platform="mac")

    def test_register_and_get(self):
        td = ToolDefinition(name="foo", description="Foo", parameters={}, handler=_dummy_handler)
        self.registry.register(td)
        assert self.registry.has_tool("foo")
        assert self.registry.get_tool("foo") is td

    def test_register_skips_wrong_platform(self):
        td = ToolDefinition(
            name="win_only", description="W", parameters={},
            handler=_dummy_handler, platforms=["windows"],
        )
        self.registry.register(td)
        assert not self.registry.has_tool("win_only")

    def test_register_all(self):
        tools = [
            ToolDefinition(name="a", description="A", parameters={}, handler=_dummy_handler),
            ToolDefinition(name="b", description="B", parameters={}, handler=_dummy_handler),
        ]
        self.registry.register_all(tools)
        assert self.registry.has_tool("a")
        assert self.registry.has_tool("b")

    def test_execute_read_only_auto(self):
        self.registry.register(ToolDefinition(
            name="read_info", description="R", parameters={},
            handler=_dummy_handler, security_level=SecurityLevel.READ_ONLY,
        ))
        result = self.registry.execute("read_info", {})
        assert result["success"] is True
        assert result["result"] == "ok"
        assert result["needs_confirmation"] is False

    def test_execute_write_needs_confirm(self):
        self.registry.register(ToolDefinition(
            name="write_thing", description="W", parameters={},
            handler=_dummy_handler, security_level=SecurityLevel.WRITE,
        ))
        result = self.registry.execute("write_thing", {})
        assert result["needs_confirmation"] is True
        assert "guard_result" in result

    def test_execute_dangerous_double_confirm(self):
        self.registry.register(ToolDefinition(
            name="nuke", description="N", parameters={},
            handler=_dummy_handler, security_level=SecurityLevel.DANGEROUS,
        ))
        result = self.registry.execute("nuke", {})
        assert result["needs_confirmation"] is True
        assert result["guard_result"].action == GuardAction.DOUBLE_CONFIRM

    def test_execute_confirmed_bypasses_guard(self):
        self.registry.register(ToolDefinition(
            name="write_thing", description="W", parameters={},
            handler=_dummy_handler, security_level=SecurityLevel.WRITE,
        ))
        result = self.registry.execute_confirmed("write_thing", {})
        assert result["success"] is True
        assert result["result"] == "ok"

    def test_execute_unknown_tool(self):
        result = self.registry.execute("nonexistent", {})
        assert result["success"] is False
        assert "未知工具" in result["result"]

    def test_execute_handler_error(self):
        self.registry.register(ToolDefinition(
            name="bad", description="B", parameters={},
            handler=_error_handler, security_level=SecurityLevel.READ_ONLY,
        ))
        result = self.registry.execute("bad", {})
        assert result["success"] is False
        assert "boom" in result["result"]

    def test_execute_blocked_tool(self):
        guard = SafeGuard(policies=[])
        guard.block_tool("forbidden")
        registry = ToolRegistry(current_platform="mac", safe_guard=guard)
        registry.register(ToolDefinition(
            name="forbidden", description="F", parameters={},
            handler=_dummy_handler, security_level=SecurityLevel.READ_ONLY,
        ))
        result = registry.execute("forbidden", {})
        assert result["success"] is False
        assert "阻止" in result["result"]

    def test_get_openai_tools(self):
        self.registry.register(ToolDefinition(
            name="t1", description="T1",
            parameters={"type": "object", "properties": {}},
            handler=_dummy_handler,
        ))
        self.registry.register(ToolDefinition(
            name="t2", description="T2",
            parameters={"type": "object", "properties": {}},
            handler=_dummy_handler,
        ))
        tools = self.registry.get_openai_tools()
        assert len(tools) == 2
        names = [t["function"]["name"] for t in tools]
        assert "t1" in names
        assert "t2" in names

    def test_list_tools(self):
        self.registry.register(ToolDefinition(name="x", description="X", parameters={}, handler=_dummy_handler))
        assert "x" in self.registry.list_tools()

    def test_get_tools_by_level(self):
        self.registry.register(ToolDefinition(
            name="ro", description="RO", parameters={},
            handler=_dummy_handler, security_level=SecurityLevel.READ_ONLY,
        ))
        self.registry.register(ToolDefinition(
            name="wr", description="WR", parameters={},
            handler=_dummy_handler, security_level=SecurityLevel.WRITE,
        ))
        ro_tools = self.registry.get_tools_by_level(SecurityLevel.READ_ONLY)
        assert len(ro_tools) == 1
        assert ro_tools[0].name == "ro"

    def test_handler_dict_result(self):
        def dict_handler(**kwargs):
            return {"success": True, "output": "done", "extra": 42}

        self.registry.register(ToolDefinition(
            name="dict_tool", description="D", parameters={},
            handler=dict_handler, security_level=SecurityLevel.READ_ONLY,
        ))
        result = self.registry.execute("dict_tool", {})
        assert result["success"] is True
        assert result["output"] == "done"
        assert result["needs_confirmation"] is False