"""LLM 客户端流式调用测试"""
from unittest.mock import MagicMock, patch

from voice_assistant.agent.llm_client import (
    StreamEvent,
    _merge_tool_call_deltas,
    call_llm_with_tools_stream,
)


class TestStreamEvent:
    def test_token_event(self):
        e = StreamEvent(type="token", content="hello")
        assert e.type == "token"
        assert e.content == "hello"
        assert e.tool_calls is None

    def test_tool_calls_event(self):
        e = StreamEvent(type="tool_calls", tool_calls=[{"id": "1", "name": "test"}])
        assert e.type == "tool_calls"
        assert e.tool_calls[0]["name"] == "test"

    def test_error_event(self):
        e = StreamEvent(type="error", content="timeout")
        assert e.type == "error"

    def test_done_event(self):
        e = StreamEvent(type="done", finish_reason="stop")
        assert e.finish_reason == "stop"


def _make_delta(index=None, id=None, func_name=None, func_args=None, content=None):
    """创建 litellm 格式的 delta 对象"""
    delta = MagicMock()
    delta.content = content
    delta.index = index
    delta.id = id
    if func_name is not None or func_args is not None:
        delta.function = MagicMock()
        delta.function.name = func_name
        delta.function.arguments = func_args
    else:
        delta.function = None
    return delta


class TestMergeToolCallDeltas:
    def test_single_tool_call(self):
        accumulated = []
        accumulated = _merge_tool_call_deltas(accumulated, _make_delta(
            index=0, id="call_1", func_name="open_file", func_args=""
        ))
        accumulated = _merge_tool_call_deltas(accumulated, _make_delta(
            index=0, func_args='{"file":'
        ))
        accumulated = _merge_tool_call_deltas(accumulated, _make_delta(
            index=0, func_args='"test.py"}'
        ))
        assert len(accumulated) == 1
        assert accumulated[0]["id"] == "call_1"
        assert accumulated[0]["name"] == "open_file"
        assert accumulated[0]["arguments"] == '{"file":"test.py"}'

    def test_multiple_tool_calls(self):
        accumulated = []
        accumulated = _merge_tool_call_deltas(accumulated, _make_delta(
            index=0, id="call_1", func_name="read", func_args=""
        ))
        accumulated = _merge_tool_call_deltas(accumulated, _make_delta(
            index=1, id="call_2", func_name="write", func_args=""
        ))
        assert len(accumulated) == 2
        assert accumulated[0]["name"] == "read"
        assert accumulated[1]["name"] == "write"

    def test_empty_accumulated(self):
        accumulated = []
        result = _merge_tool_call_deltas(accumulated, _make_delta(
            index=0, id="call_x", func_name="test", func_args="{}"
        ))
        assert len(result) == 1
        assert result[0]["arguments"] == "{}"


class TestCallLLMWithToolsStream:
    """测试流式 LLM 调用（Mock litellm）"""

    def _setup_model_manager(self, mock_mm):
        mock_mm.get_queue.return_value = None
        mock_model = MagicMock()
        mock_model.name = "test-model"
        mock_model.litellm_model = "openai/test-model"
        mock_model.base_url = "http://localhost"
        mock_model.api_key = "test-key"
        mock_mm.get_current_model.return_value = mock_model
        mock_mm.build_model_queue.return_value = None

    def _make_chunk(self, delta_content=None, tool_calls=None, finish_reason=None):
        """创建 litellm 格式的流式 chunk"""
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta = MagicMock()
        chunk.choices[0].delta.content = delta_content
        if tool_calls is not None:
            chunk.choices[0].delta.tool_calls = tool_calls
        else:
            chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = finish_reason
        return chunk

    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_stream_text_response(self, mock_completion, mock_mm, mock_limiter, mock_validate):
        """流式文本响应生成 token 事件"""
        chunks = [
            self._make_chunk(delta_content="Hello"),
            self._make_chunk(delta_content=" world"),
            self._make_chunk(finish_reason="stop"),
        ]
        mock_completion.return_value = iter(chunks)
        self._setup_model_manager(mock_mm)

        events = list(call_llm_with_tools_stream("hello", []))

        token_events = [e for e in events if e.type == "token"]
        done_events = [e for e in events if e.type == "done"]

        assert len(token_events) == 2
        assert token_events[0].content == "Hello"
        assert token_events[1].content == " world"
        assert len(done_events) == 1
        assert done_events[0].finish_reason == "stop"

    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_stream_tool_calls_response(self, mock_completion, mock_mm, mock_limiter, mock_validate):
        """流式 tool_calls 响应组装正确"""
        tc_delta1 = _make_delta(index=0, id="call_1", func_name="open_file", func_args="")
        tc_delta2 = _make_delta(index=0, func_args='{"file"}')

        chunks = [
            self._make_chunk(tool_calls=[tc_delta1]),
            self._make_chunk(tool_calls=[tc_delta2]),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        mock_completion.return_value = iter(chunks)
        self._setup_model_manager(mock_mm)

        events = list(call_llm_with_tools_stream("open file", [{"type": "function", "function": {"name": "open_file"}}]))

        tc_events = [e for e in events if e.type == "tool_calls"]
        done_events = [e for e in events if e.type == "done"]

        assert len(tc_events) == 1
        assert tc_events[0].tool_calls[0]["name"] == "open_file"
        assert done_events[0].finish_reason == "tool_calls"

    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_stream_api_error(self, mock_completion, mock_mm, mock_limiter, mock_validate):
        """API 错误生成 error 事件"""
        import litellm
        mock_completion.side_effect = litellm.APIError(
            message="server error", llm_provider="openai", model="test-model", status_code=500
        )
        self._setup_model_manager(mock_mm)

        events = list(call_llm_with_tools_stream("hello", []))
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) == 1

    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    def test_stream_no_model(self, mock_mm, mock_limiter, mock_validate):
        """无可用模型生成 error 事件"""
        mock_mm.get_queue.return_value = None
        mock_mm.get_current_model.return_value = None
        mock_mm.build_model_queue.return_value = None

        events = list(call_llm_with_tools_stream("hello", []))
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) == 1
        assert "模型" in error_events[0].content
