"""VoiceSession.process_text_stream() 测试"""
import pytest
from unittest.mock import patch, MagicMock

from voice_assistant.core.session import VoiceSession, ProcessResult
from voice_assistant.agent.orchestrator import AgentEvent, AgentResult
from voice_assistant.model.intent import Intent, IntentType


def _make_session_with_orchestrator():
    """构建带 mock orchestrator 的 VoiceSession"""
    session = VoiceSession(auto_mode=True)
    session._initialized = True
    session._asr = MagicMock()
    session._tts = MagicMock()
    session._chat_executor = MagicMock()
    session._computer_executor = MagicMock()
    session._router = MagicMock()
    return session


class TestProcessTextStream:
    """测试 process_text_stream() 方法"""

    def test_empty_input_yields_complete(self):
        """空输入直接返回 complete 事件"""
        session = _make_session_with_orchestrator()
        events = list(session.process_text_stream("  "))

        assert len(events) == 1
        assert events[0].type == "complete"
        assert events[0].result.intent_type == "unknown"

    @patch("voice_assistant.core.session.simple_classify_intent")
    def test_chat_intent_yields_complete(self, mock_classify):
        """chat 意图返回单个 complete 事件"""
        mock_classify.return_value = Intent(
            intent_type=IntentType.ORDINARY_CHAT, original_text="你好", confidence=0.9
        )
        mock_router = MagicMock()
        mock_router.route.return_value = {
            "response": "你好！",
            "history_updated": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "你好！"}],
        }

        session = _make_session_with_orchestrator()
        session._router = mock_router
        session._orchestrator = None

        events = list(session.process_text_stream("你好"))

        complete_events = [e for e in events if e.type == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0].result.response == "你好！"

    @patch("voice_assistant.core.session.simple_classify_intent")
    def test_computer_control_with_orchestrator(self, mock_classify):
        """computer_control 意图走 orchestrator 流式路径"""
        mock_classify.return_value = Intent(
            intent_type=IntentType.COMPUTER_CONTROL, original_text="打开文件", confidence=0.95
        )

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

        session = _make_session_with_orchestrator()
        session._orchestrator = mock_orch

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
        assert complete_events[0].result.intent_type == "computer"
        assert complete_events[0].result.history_updated is True

    @patch("voice_assistant.core.session.simple_classify_intent")
    def test_orchestrator_error_falls_back(self, mock_classify):
        """orchestrator 流式错误时回退到同步路径"""
        mock_classify.return_value = Intent(
            intent_type=IntentType.COMPUTER_CONTROL, original_text="打开文件", confidence=0.95
        )

        mock_orch = MagicMock()
        mock_orch.run_stream.side_effect = RuntimeError("LLM 超时")

        mock_router = MagicMock()
        mock_router.route.return_value = {
            "response": "回退响应",
            "history_updated": [],
        }

        session = _make_session_with_orchestrator()
        session._orchestrator = mock_orch
        session._router = mock_router

        events = list(session.process_text_stream("打开文件"))

        complete_events = [e for e in events if e.type == "complete"]
        assert len(complete_events) >= 1

    def test_auto_mode_false_yields_complete(self):
        """非自动模式直接走 chat executor"""
        session = _make_session_with_orchestrator()
        session._auto_mode = False
        session._chat_executor.execute.return_value = {"response": "你好！"}

        events = list(session.process_text_stream("你好"))

        complete_events = [e for e in events if e.type == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0].result.response == "你好！"
        assert complete_events[0].result.intent_type == "chat"

    @patch("voice_assistant.core.session.simple_classify_intent")
    def test_intent_callback_called(self, mock_classify):
        """意图检测回调被正确调用"""
        mock_classify.return_value = Intent(
            intent_type=IntentType.ORDINARY_CHAT, original_text="hi", confidence=0.8
        )
        mock_router = MagicMock()
        mock_router.route.return_value = {"response": "ok"}

        detected = []
        session = _make_session_with_orchestrator()
        session._on_intent_detected = lambda t, c: detected.append((t, c))
        session._router = mock_router
        session._orchestrator = None

        list(session.process_text_stream("hi"))

        assert len(detected) == 1
        assert detected[0][0] == "ordinary_chat"