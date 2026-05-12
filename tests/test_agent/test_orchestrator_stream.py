"""AgentOrchestrator.run_stream() 测试"""
import pytest
from unittest.mock import patch, MagicMock

from voice_assistant.agent.orchestrator import AgentOrchestrator, AgentEvent, AgentResult
from voice_assistant.agent.llm_client import StreamEvent


def _make_registry():
    """构建 mock ToolRegistry"""
    registry = MagicMock()
    registry.get_openai_tools.return_value = [{"type": "function", "function": {"name": "test_tool"}}]
    registry.execute.return_value = {"success": True, "result": "ok"}
    return registry


class TestAgentEvent:
    def test_llm_token_event(self):
        e = AgentEvent(type="llm_token", content="hello")
        assert e.type == "llm_token"
        assert e.content == "hello"
        assert e.tool_name is None

    def test_tool_start_event(self):
        e = AgentEvent(type="tool_start", tool_name="open_file", tool_arguments={"file": "a.py"})
        assert e.type == "tool_start"
        assert e.tool_name == "open_file"
        assert e.tool_arguments == {"file": "a.py"}

    def test_tool_result_event(self):
        e = AgentEvent(type="tool_result", tool_name="open_file", tool_result="done", success=True)
        assert e.type == "tool_result"
        assert e.success is True

    def test_complete_event(self):
        result = AgentResult(success=True, response="done")
        e = AgentEvent(type="complete", result=result)
        assert e.type == "complete"
        assert e.result.success is True

    def test_error_event(self):
        e = AgentEvent(type="error", content="timeout")
        assert e.type == "error"
        assert e.content == "timeout"


class TestAgentOrchestratorStream:
    """测试 run_stream() 生成器"""

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_text_response_stream(self, mock_stream):
        """流式文本响应生成 llm_token + complete 事件"""
        mock_stream.return_value = iter([
            StreamEvent(type="token", content="Hello"),
            StreamEvent(type="token", content=" world"),
            StreamEvent(type="done", finish_reason="stop"),
        ])

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("hello"))

        token_events = [e for e in events if e.type == "llm_token"]
        complete_events = [e for e in events if e.type == "complete"]

        assert len(token_events) == 2
        assert token_events[0].content == "Hello"
        assert token_events[1].content == " world"
        assert len(complete_events) == 1
        assert complete_events[0].result.success is True
        assert complete_events[0].result.response == "Hello world"

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_tool_call_stream(self, mock_stream):
        """流式 tool_calls 响应生成 tool_start + tool_result + complete 事件"""
        tool_calls = [{"id": "call_1", "name": "open_file", "arguments": {"file": "test.py"}}]

        # 第一轮：LLM 返回 tool_calls
        first_iter = iter([
            StreamEvent(type="tool_calls", tool_calls=tool_calls, finish_reason="tool_calls"),
            StreamEvent(type="done", finish_reason="tool_calls"),
        ])
        # 第二轮：LLM 返回文本总结
        second_iter = iter([
            StreamEvent(type="token", content="已打开文件"),
            StreamEvent(type="done", finish_reason="stop"),
        ])
        mock_stream.side_effect = [first_iter, second_iter]

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("打开文件"))

        start_events = [e for e in events if e.type == "tool_start"]
        result_events = [e for e in events if e.type == "tool_result"]
        complete_events = [e for e in events if e.type == "complete"]

        assert len(start_events) == 1
        assert start_events[0].tool_name == "open_file"
        assert len(result_events) == 1
        assert result_events[0].success is True
        assert len(complete_events) == 1
        assert "已打开文件" in complete_events[0].result.response

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_error_stream(self, mock_stream):
        """流式错误生成 error + complete 事件"""
        mock_stream.return_value = iter([
            StreamEvent(type="error", content="API 500 error"),
        ])

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("hello"))

        error_events = [e for e in events if e.type == "error"]
        complete_events = [e for e in events if e.type == "complete"]

        assert len(error_events) == 1
        assert "API 500" in error_events[0].content
        assert len(complete_events) == 1
        assert complete_events[0].result.success is False

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_no_tool_call_stops(self, mock_stream):
        """无 tool call 时正确结束"""
        mock_stream.return_value = iter([
            StreamEvent(type="done", finish_reason="stop"),
        ])

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=3)
        events = list(orch.run_stream("hello"))

        complete_events = [e for e in events if e.type == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0].result.success is True

    @patch("voice_assistant.agent.orchestrator.call_llm_with_tools_stream")
    def test_max_iterations_stream(self, mock_stream):
        """达到最大迭代次数时返回部分完成"""
        tool_calls = [{"id": "c1", "name": "loop_tool", "arguments": {}}]

        # 每轮都返回 tool_calls，永不停止
        def infinite_tool_calls(*args, **kwargs):
            return iter([
                StreamEvent(type="tool_calls", tool_calls=tool_calls, finish_reason="tool_calls"),
                StreamEvent(type="done", finish_reason="tool_calls"),
            ])

        mock_stream.side_effect = infinite_tool_calls

        registry = _make_registry()
        orch = AgentOrchestrator(tool_registry=registry, max_iterations=2)
        events = list(orch.run_stream("keep going"))

        complete_events = [e for e in events if e.type == "complete"]
        assert len(complete_events) == 1
        assert "部分完成" in complete_events[0].result.response

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

        complete_events = [e for e in events if e.type == "complete"]
        assert len(complete_events) == 1
        assert "确认" in complete_events[0].result.response