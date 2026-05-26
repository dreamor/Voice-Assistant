"""AgentOrchestrator.run_stream() 测试"""
from unittest.mock import MagicMock, patch

from voice_assistant.agent.events import AgentEvent, AgentResult, EventType
from voice_assistant.agent.llm_client import StreamEvent
from voice_assistant.agent.orchestrator import AgentOrchestrator


def _make_registry():
    """构建 mock ToolRegistry"""
    registry = MagicMock()
    registry.get_openai_tools.return_value = [{"type": "function", "function": {"name": "test_tool"}}]
    registry.execute.return_value = {"success": True, "result": "ok"}
    return registry


class TestAgentEvent:
    def test_message_delta_event(self):
        e = AgentEvent(type=EventType.MESSAGE_DELTA, content="hello")
        assert e.type == EventType.MESSAGE_DELTA
        assert e.content == "hello"
        assert e.tool_name is None

    def test_tool_call_event(self):
        e = AgentEvent(type=EventType.TOOL_CALL, tool_name="open_file", tool_arguments={"file": "a.py"})
        assert e.type == EventType.TOOL_CALL
        assert e.tool_name == "open_file"
        assert e.tool_arguments == {"file": "a.py"}

    def test_tool_execution_start_event(self):
        e = AgentEvent(type=EventType.TOOL_EXECUTION_START, tool_name="open_file", tool_call_id="call_1")
        assert e.type == EventType.TOOL_EXECUTION_START
        assert e.tool_call_id == "call_1"

    def test_tool_execution_end_event(self):
        e = AgentEvent(
            type=EventType.TOOL_EXECUTION_END,
            tool_name="open_file",
            tool_call_id="call_1",
            tool_result="done",
            tool_success=True,
            duration_ms=142,
        )
        assert e.type == EventType.TOOL_EXECUTION_END
        assert e.tool_success is True
        assert e.duration_ms == 142

    def test_agent_end_event(self):
        result = AgentResult(success=True, response="done")
        e = AgentEvent(type=EventType.AGENT_END, result=result)
        assert e.type == EventType.AGENT_END
        assert e.result.success is True

    def test_error_event(self):
        e = AgentEvent(type=EventType.ERROR, content="timeout")
        assert e.type == EventType.ERROR
        assert e.content == "timeout"

    def test_to_ws_message(self):
        e = AgentEvent(
            type=EventType.TOOL_EXECUTION_END,
            tool_name="open_file",
            tool_call_id="call_1",
            tool_result="file content",
            tool_success=True,
            duration_ms=50,
        )
        msg = e.to_ws_message()
        assert msg["type"] == "tool_execution_end"
        assert msg["tool_name"] == "open_file"
        assert msg["success"] is True
        assert msg["duration_ms"] == 50

    def test_to_ws_message_omits_defaults(self):
        e = AgentEvent(type=EventType.MESSAGE_DELTA, content="hi")
        msg = e.to_ws_message()
        assert msg["type"] == "message_delta"
        assert msg["content"] == "hi"
        assert "tool_name" not in msg
        assert "iteration" not in msg

    def test_legacy_type_normalization(self):
        from voice_assistant.agent.events import normalize_event_type

        assert normalize_event_type("llm_token") == EventType.MESSAGE_DELTA
        assert normalize_event_type("tool_start") == EventType.TOOL_EXECUTION_START
        assert normalize_event_type("tool_result") == EventType.TOOL_EXECUTION_END
        assert normalize_event_type("complete") == EventType.AGENT_END
        assert normalize_event_type("error") == EventType.ERROR


class TestAgentOrchestratorStream:
    """测试 run_stream() 生成器"""

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_text_response_stream(self, mock_stream):
        """流式文本响应生成 MESSAGE_DELTA + AGENT_START/END 事件"""
        mock_stream.return_value = iter([
            StreamEvent(type="token", content="Hello"),
            StreamEvent(type="token", content=" world"),
            StreamEvent(type="done", finish_reason="stop"),
        ])

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("hello"))

        type_values = [e.type for e in events]
        assert EventType.AGENT_START in type_values
        assert EventType.MESSAGE_DELTA in type_values
        assert EventType.AGENT_END in type_values

        delta_events = [e for e in events if e.type == EventType.MESSAGE_DELTA]
        assert len(delta_events) == 2
        assert delta_events[0].content == "Hello"
        assert delta_events[1].content == " world"

        end_events = [e for e in events if e.type == EventType.AGENT_END]
        assert len(end_events) == 1
        assert end_events[0].result.success is True
        assert end_events[0].result.response == "Hello world"

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_tool_call_stream(self, mock_stream):
        """流式 tool_calls 响应生成 TOOL_CALL + TOOL_EXECUTION_START/END + AGENT_END 事件"""
        tool_calls = [{"id": "call_1", "name": "open_file", "arguments": {"file": "test.py"}}]

        first_iter = iter([
            StreamEvent(type="tool_calls", tool_calls=tool_calls, finish_reason="tool_calls"),
            StreamEvent(type="done", finish_reason="tool_calls"),
        ])
        second_iter = iter([
            StreamEvent(type="token", content="已打开文件"),
            StreamEvent(type="done", finish_reason="stop"),
        ])
        mock_stream.side_effect = [first_iter, second_iter]

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("打开文件"))

        type_values = [e.type for e in events]
        assert EventType.TOOL_CALL in type_values
        assert EventType.TOOL_EXECUTION_START in type_values
        assert EventType.TOOL_EXECUTION_END in type_values
        assert EventType.AGENT_END in type_values

        call_events = [e for e in events if e.type == EventType.TOOL_CALL]
        assert len(call_events) == 1
        assert call_events[0].tool_name == "open_file"

        exec_end_events = [e for e in events if e.type == EventType.TOOL_EXECUTION_END]
        assert len(exec_end_events) == 1
        assert exec_end_events[0].tool_success is True

        end_events = [e for e in events if e.type == EventType.AGENT_END]
        assert len(end_events) == 1
        assert "已打开文件" in end_events[0].result.response

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_error_stream(self, mock_stream):
        """流式错误生成 ERROR + AGENT_END 事件"""
        mock_stream.return_value = iter([
            StreamEvent(type="error", content="API 500 error"),
        ])

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("hello"))

        type_values = [e.type for e in events]
        assert EventType.ERROR in type_values
        assert EventType.AGENT_END in type_values

        error_events = [e for e in events if e.type == EventType.ERROR]
        assert "API 500" in error_events[0].content

        end_events = [e for e in events if e.type == EventType.AGENT_END]
        assert end_events[0].result.success is False

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_no_tool_call_stops(self, mock_stream):
        """无 tool call 时正确结束"""
        mock_stream.return_value = iter([
            StreamEvent(type="done", finish_reason="stop"),
        ])

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("hello"))

        end_events = [e for e in events if e.type == EventType.AGENT_END]
        assert len(end_events) == 1
        assert end_events[0].result.success is True

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_max_iterations_stream(self, mock_stream):
        """达到最大迭代次数时返回部分完成"""
        tool_calls = [{"id": "c1", "name": "loop_tool", "arguments": {}}]

        def infinite_tool_calls(*args, **kwargs):
            return iter([
                StreamEvent(type="tool_calls", tool_calls=tool_calls, finish_reason="tool_calls"),
                StreamEvent(type="done", finish_reason="tool_calls"),
            ])

        mock_stream.side_effect = infinite_tool_calls

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=2)
        events = list(orch.run_stream("keep going"))

        end_events = [e for e in events if e.type == EventType.AGENT_END]
        assert len(end_events) == 1
        assert "部分完成" in end_events[0].result.response

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_needs_confirmation_no_callback(self, mock_stream):
        """需要确认但无回调时返回确认消息"""
        tool_calls = [{"id": "c1", "name": "delete_file", "arguments": {"file": "a.py"}}]

        mock_stream.return_value = iter([
            StreamEvent(type="tool_calls", tool_calls=tool_calls, finish_reason="tool_calls"),
            StreamEvent(type="done", finish_reason="tool_calls"),
        ])

        registry = _make_registry()
        registry.execute.return_value = {
            "needs_confirmation": True,
            "guard_result": MagicMock(message="此操作需要确认"),
        }
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("删除文件"))

        end_events = [e for e in events if e.type == EventType.AGENT_END]
        assert len(end_events) == 1
        assert "确认" in end_events[0].result.response

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_turn_events(self, mock_stream):
        """每轮迭代生成 TURN_START/TURN_END 事件"""
        mock_stream.return_value = iter([
            StreamEvent(type="token", content="Hi"),
            StreamEvent(type="done", finish_reason="stop"),
        ])

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("hello"))

        type_values = [e.type for e in events]
        assert EventType.TURN_START in type_values
        assert EventType.TURN_END in type_values

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_tool_execution_timing(self, mock_stream):
        """工具执行事件包含 duration_ms"""
        tool_calls = [{"id": "c1", "name": "test_tool", "arguments": {}}]

        mock_stream.side_effect = [
            iter([
                StreamEvent(type="tool_calls", tool_calls=tool_calls, finish_reason="tool_calls"),
                StreamEvent(type="done", finish_reason="tool_calls"),
            ]),
            iter([
                StreamEvent(type="token", content="done"),
                StreamEvent(type="done", finish_reason="stop"),
            ]),
        ]

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("test"))

        exec_end = [e for e in events if e.type == EventType.TOOL_EXECUTION_END]
        assert len(exec_end) == 1
        assert exec_end[0].duration_ms is not None
        assert exec_end[0].duration_ms >= 0
