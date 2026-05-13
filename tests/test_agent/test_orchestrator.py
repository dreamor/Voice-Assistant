"""AgentOrchestrator 单元测试"""
from unittest.mock import MagicMock, patch

from voice_assistant.agent.orchestrator import MAX_ITERATIONS, AgentOrchestrator, AgentResult
from voice_assistant.security.safe_guard import SecurityLevel
from voice_assistant.tools.registry import ToolDefinition, ToolRegistry


def _echo_handler(**kwargs):
    return f"echo: {kwargs}"


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry(current_platform="mac")
    registry.register(ToolDefinition(
        name="read_info", description="Read info",
        parameters={"type": "object", "properties": {"key": {"type": "string"}}},
        handler=_echo_handler,
        security_level=SecurityLevel.READ_ONLY,
    ))
    registry.register(ToolDefinition(
        name="write_thing", description="Write something",
        parameters={"type": "object", "properties": {"data": {"type": "string"}}},
        handler=_echo_handler,
        security_level=SecurityLevel.WRITE,
    ))
    return registry


class TestAgentResult:
    def test_defaults(self):
        r = AgentResult(success=True, response="ok")
        assert r.tool_calls_made == []
        assert r.confirmations_needed == []
        assert r.iterations == 0
        assert r.fallback_used is False


class TestAgentOrchestrator:
    def test_init_defaults(self):
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry)
        assert orch._max_iterations == MAX_ITERATIONS
        assert orch._confirm_callback is None

    def test_init_custom_iterations(self):
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        assert orch._max_iterations == 3

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_text_response_stops_loop(self, mock_llm):
        mock_llm.return_value = {
            "finish_reason": "stop",
            "content": "你好！有什么可以帮你的？",
            "tool_calls": None,
        }
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry)
        result = orch.run("你好")

        assert result.success is True
        assert result.response == "你好！有什么可以帮你的？"
        assert result.iterations == 1
        assert result.tool_calls_made == []
        mock_llm.assert_called_once()

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_tool_call_read_only_auto_executes(self, mock_llm):
        mock_llm.side_effect = [
            {
                "finish_reason": "tool_calls",
                "content": None,
                "tool_calls": [{
                    "id": "tc1",
                    "name": "read_info",
                    "arguments": {"key": "cpu"},
                }],
            },
            {
                "finish_reason": "stop",
                "content": "CPU 使用率 45%",
                "tool_calls": None,
            },
        ]
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry)
        result = orch.run("查看 CPU 使用率")

        assert result.success is True
        assert "CPU" in result.response
        assert "read_info" in result.tool_calls_made
        assert result.iterations == 2

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_tool_call_write_needs_confirm_no_callback(self, mock_llm):
        mock_llm.return_value = {
            "finish_reason": "tool_calls",
            "content": None,
            "tool_calls": [{
                "id": "tc1",
                "name": "write_thing",
                "arguments": {"data": "hello"},
            }],
        }
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry)
        result = orch.run("写入数据")

        # No confirm callback → auto-reject
        assert result.success is True
        assert "确认" in result.response
        assert result.tool_calls_made == []

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_tool_call_write_confirmed(self, mock_llm):
        mock_llm.side_effect = [
            {
                "finish_reason": "tool_calls",
                "content": None,
                "tool_calls": [{
                    "id": "tc1",
                    "name": "write_thing",
                    "arguments": {"data": "hello"},
                }],
            },
            {
                "finish_reason": "stop",
                "content": "已写入完成",
                "tool_calls": None,
            },
        ]
        confirm_cb = MagicMock(return_value=True)
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, confirm_callback=confirm_cb)
        result = orch.run("写入数据")

        assert result.success is True
        assert "写入" in result.response
        assert "write_thing" in result.tool_calls_made
        confirm_cb.assert_called_once()

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_tool_call_write_rejected(self, mock_llm):
        mock_llm.return_value = {
            "finish_reason": "tool_calls",
            "content": None,
            "tool_calls": [{
                "id": "tc1",
                "name": "write_thing",
                "arguments": {"data": "hello"},
            }],
        }
        confirm_cb = MagicMock(return_value=False)
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, confirm_callback=confirm_cb)
        result = orch.run("写入数据")

        assert result.success is True
        assert "确认" in result.response
        assert result.tool_calls_made == []

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_max_iterations_reached(self, mock_llm):
        mock_llm.return_value = {
            "finish_reason": "tool_calls",
            "content": None,
            "tool_calls": [{
                "id": "tc1",
                "name": "read_info",
                "arguments": {"key": "x"},
            }],
        }
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=2)
        result = orch.run("一直读")

        assert result.success is True
        assert result.iterations == 2

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_llm_error_returns_failure(self, mock_llm):
        mock_llm.return_value = {
            "finish_reason": "error",
            "content": "服务不可用",
            "tool_calls": None,
        }
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry)
        result = orch.run("测试错误")

        assert result.success is False
        assert "不可用" in result.response

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_no_tool_calls_stops(self, mock_llm):
        mock_llm.return_value = {
            "finish_reason": "stop",
            "content": "",
            "tool_calls": None,
        }
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry)
        result = orch.run("空回复")

        assert result.success is True
        assert result.iterations == 1

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_run_with_confirm_approved(self, mock_llm):
        mock_llm.return_value = {
            "finish_reason": "stop",
            "content": "操作完成",
            "tool_calls": None,
        }
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry)
        result = orch.run_with_confirm(
            user_text="写入",
            pending_confirm={"tool_name": "write_thing", "arguments": {"data": "x"}, "approved": True},
        )
        assert result.success is True

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools")
    def test_run_with_confirm_rejected(self, mock_llm):
        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry)
        result = orch.run_with_confirm(
            user_text="写入",
            pending_confirm={"tool_name": "write_thing", "arguments": {"data": "x"}, "approved": False},
        )
        assert result.success is True
        assert "取消" in result.response
