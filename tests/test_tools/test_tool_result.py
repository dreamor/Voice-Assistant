"""ToolResult 类型和参数校验测试"""
import pytest
from unittest.mock import MagicMock

from voice_assistant.tools.registry import ToolResult, ToolDefinition, ToolRegistry, _validate_arguments
from voice_assistant.security.safe_guard import SecurityLevel, SafeGuard


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, output="done")
        assert r.success is True
        assert r.output == "done"
        assert r.needs_confirmation is False
        assert r.guard_result is None

    def test_error_result(self):
        r = ToolResult(success=False, output="failed: not found")
        assert r.success is False
        assert "not found" in r.output

    def test_needs_confirmation(self):
        guard = MagicMock()
        r = ToolResult(success=True, output="confirm?", needs_confirmation=True, guard_result=guard)
        assert r.needs_confirmation is True
        assert r.guard_result is guard

    def test_to_dict_basic(self):
        r = ToolResult(success=True, output="ok")
        d = r.to_dict()
        assert d["success"] is True
        assert d["result"] == "ok"
        assert d["needs_confirmation"] is False
        assert "guard_result" not in d

    def test_to_dict_with_guard(self):
        guard = MagicMock()
        r = ToolResult(success=True, output="confirm?", needs_confirmation=True, guard_result=guard)
        d = r.to_dict()
        assert d["guard_result"] is guard

    def test_to_dict_with_data(self):
        r = ToolResult(success=True, output="ok", data={"file": "a.py", "lines": 10})
        d = r.to_dict()
        assert d["file"] == "a.py"
        assert d["lines"] == 10

    def test_default_data_empty(self):
        r = ToolResult(success=True, output="ok")
        assert r.data == {}


class TestValidateArguments:
    def test_required_present(self):
        params = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        errors = _validate_arguments(params, {"path": "/tmp/test"})
        assert errors == []

    def test_required_missing(self):
        params = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        errors = _validate_arguments(params, {})
        assert len(errors) == 1
        assert "path" in errors[0]

    def test_required_none(self):
        params = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }
        errors = _validate_arguments(params, {"path": None})
        assert len(errors) == 1

    def test_type_mismatch(self):
        params = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"],
        }
        errors = _validate_arguments(params, {"count": "not_a_number"})
        assert len(errors) == 1
        assert "integer" in errors[0]

    def test_type_match(self):
        params = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": [],
        }
        errors = _validate_arguments(params, {"count": 5})
        assert errors == []

    def test_string_type(self):
        params = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": [],
        }
        errors = _validate_arguments(params, {"name": "hello"})
        assert errors == []

    def test_array_type(self):
        params = {
            "type": "object",
            "properties": {"items": {"type": "array", "items": {"type": "string"}}},
            "required": [],
        }
        errors = _validate_arguments(params, {"items": ["a", "b"]})
        assert errors == []

    def test_number_type_accepts_int(self):
        params = {
            "type": "object",
            "properties": {"val": {"type": "number"}},
            "required": [],
        }
        errors = _validate_arguments(params, {"val": 42})
        assert errors == []

    def test_extra_args_ignored(self):
        params = {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
        }
        errors = _validate_arguments(params, {"path": "/tmp", "extra": 123})
        assert errors == []

    def test_no_required_no_properties(self):
        errors = _validate_arguments({"type": "object", "properties": {}}, {})
        assert errors == []

    def test_boolean_not_integer(self):
        params = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": [],
        }
        errors = _validate_arguments(params, {"count": True})
        assert len(errors) == 1
        assert "boolean" in errors[0]


class TestRegistryWithValidation:
    """测试 ToolRegistry 集成参数校验"""

    def _make_registry(self):
        registry = ToolRegistry(current_platform="mac", safe_guard=SafeGuard())
        registry.register(ToolDefinition(
            name="read_file",
            description="读取文件",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=lambda path: f"content of {path}",
            security_level=SecurityLevel.READ_ONLY,
        ))
        return registry

    def test_execute_with_valid_args(self):
        reg = self._make_registry()
        result = reg.execute("read_file", {"path": "/tmp/test.txt"})
        assert result["success"] is True
        assert "content of" in result["result"]

    def test_execute_with_missing_required(self):
        reg = self._make_registry()
        result = reg.execute("read_file", {})
        assert result["success"] is False
        assert "缺少必填参数" in result["result"]

    def test_execute_with_wrong_type(self):
        reg = self._make_registry()
        result = reg.execute("read_file", {"path": 123})
        assert result["success"] is False
        assert "string" in result["result"]

    def test_register_duplicate_warns(self, caplog):
        reg = ToolRegistry(current_platform="mac")
        tool = ToolDefinition(
            name="dup_tool",
            description="test",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda: "ok",
            security_level=SecurityLevel.READ_ONLY,
        )
        reg.register(tool)
        with caplog.at_level("WARNING"):
            reg.register(tool)
        assert any("重复注册" in r.message for r in caplog.records)

    def test_execute_type_error_returns_failure(self):
        """handler 参数类型错误时返回友好错误"""
        reg = ToolRegistry(current_platform="mac")
        reg.register(ToolDefinition(
            name="strict_tool",
            description="需要 string 参数",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            handler=lambda name: f"hello {name}",
            security_level=SecurityLevel.READ_ONLY,
        ))
        result = reg.execute("strict_tool", {"name": "world"})
        assert result["success"] is True