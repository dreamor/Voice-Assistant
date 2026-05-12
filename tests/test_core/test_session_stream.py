"""VoiceSession.process_text_stream() 测试

精简后的 Session 始终走 orchestrator，单一路径。
"""
from unittest.mock import MagicMock

from voice_assistant.agent.orchestrator import AgentEvent, AgentResult
from voice_assistant.core.session import VoiceSession


def _make_session(mock_orchestrator):
    session = VoiceSession()
    session._initialized = True
    session._asr = MagicMock()
    session._tts = MagicMock()
    session._orchestrator = mock_orchestrator
    return session


class TestProcessTextStream:
    def test_empty_input_yields_complete(self):
        session = _make_session(MagicMock())
        events = list(session.process_text_stream("  "))

        assert len(events) == 1
        assert events[0].type == "complete"
        assert events[0].result.intent_type == "unknown"

    def test_orchestrator_events_passthrough(self):
        mock_orch = MagicMock()
        mock_orch.run_stream.return_value = iter([
            AgentEvent(type="llm_token", content="正在"),
            AgentEvent(type="llm_token", content="打开"),
            AgentEvent(type="tool_start", tool_name="open_file", tool_arguments={"file": "a.py"}),
            AgentEvent(type="tool_result", tool_name="open_file", tool_result="ok", success=True),
            AgentEvent(type="complete", result=AgentResult(
                success=True, response="已打开文件", tool_calls_made=["open_file"],
            )),
        ])
        session = _make_session(mock_orch)

        events = list(session.process_text_stream("打开文件"))

        token_events = [e for e in events if e.type == "llm_token"]
        start_events = [e for e in events if e.type == "tool_start"]
        result_events = [e for e in events if e.type == "tool_result"]
        complete_events = [e for e in events if e.type == "complete"]

        assert len(token_events) == 2
        assert token_events[0].content == "正在"
        assert len(start_events) == 1
        assert start_events[0].tool_name == "open_file"
        assert len(result_events) == 1
        assert len(complete_events) == 1
        assert complete_events[0].result.intent_type == "agent"
        assert complete_events[0].result.history_updated is True
        assert complete_events[0].result.execution_output == "open_file"

    def test_history_updated_after_complete(self):
        mock_orch = MagicMock()
        mock_orch.run_stream.return_value = iter([
            AgentEvent(type="complete", result=AgentResult(
                success=True, response="你好！", tool_calls_made=[],
            )),
        ])
        session = _make_session(mock_orch)

        list(session.process_text_stream("你好"))

        history = session.get_history()
        assert history[-2] == {"role": "user", "content": "你好"}
        assert history[-1] == {"role": "assistant", "content": "你好！"}

    def test_orchestrator_error_yields_error_event(self):
        mock_orch = MagicMock()
        mock_orch.run_stream.side_effect = RuntimeError("LLM 超时")
        session = _make_session(mock_orch)

        events = list(session.process_text_stream("打开文件"))

        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) == 1
        assert "LLM 超时" in error_events[0].content

    def test_execution_callbacks_fire(self):
        mock_orch = MagicMock()
        mock_orch.run_stream.return_value = iter([
            AgentEvent(type="complete", result=AgentResult(success=True, response="ok")),
        ])
        starts, ends = [], []
        session = _make_session(mock_orch)
        session._on_execution_start = lambda: starts.append(1)
        session._on_execution_end = lambda: ends.append(1)

        list(session.process_text_stream("hi"))

        assert starts == [1]
        assert ends == [1]
