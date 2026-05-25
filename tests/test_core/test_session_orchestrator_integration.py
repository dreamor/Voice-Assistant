"""VoiceSession 与 AgentOrchestrator 集成测试

测试 extra_system 传递、tool group hint 注入、history 裁剪协同。
"""
from unittest.mock import MagicMock, patch

import pytest

from voice_assistant.core.session import VoiceSession, _build_tool_group_hint


class TestExtraSystemPassedToOrchestrator:
    """验证 extra_system 参数正确传递到 orchestrator.run / run_stream"""

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="skill_hint")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_process_text_passes_skill_addendum(self, mock_init, mock_skill, mock_group):
        session = VoiceSession()
        session._initialized = True

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "done"
        mock_result.tool_calls_made = []
        mock_orchestrator.run.return_value = mock_result
        session._orchestrator = mock_orchestrator

        session.process_text("hello")
        call_kwargs = mock_orchestrator.run.call_args
        assert call_kwargs.kwargs.get("extra_system") == "skill_hint" or \
            (len(call_kwargs.args) > 2 and "skill_hint" in str(call_kwargs))

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="group_hint")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="skill_hint")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_process_text_appends_group_hint(self, mock_init, mock_skill, mock_group):
        session = VoiceSession()
        session._initialized = True

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "done"
        mock_result.tool_calls_made = []
        mock_orchestrator.run.return_value = mock_result
        session._orchestrator = mock_orchestrator

        session.process_text("hello")
        call_kwargs = mock_orchestrator.run.call_args
        extra_system = call_kwargs.kwargs.get("extra_system", "")
        assert "skill_hint" in extra_system
        assert "group_hint" in extra_system

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="group_hint")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_process_text_group_hint_only(self, mock_init, mock_skill, mock_group):
        """skill_addendum 为空时，group_hint 仍应传递"""
        session = VoiceSession()
        session._initialized = True

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "done"
        mock_result.tool_calls_made = []
        mock_orchestrator.run.return_value = mock_result
        session._orchestrator = mock_orchestrator

        session.process_text("hello")
        call_kwargs = mock_orchestrator.run.call_args
        extra_system = call_kwargs.kwargs.get("extra_system", "")
        assert extra_system == "group_hint"

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_process_text_no_hints(self, mock_init, mock_skill, mock_group):
        """两者都为空时，extra_system 为空字符串"""
        session = VoiceSession()
        session._initialized = True

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "done"
        mock_result.tool_calls_made = []
        mock_orchestrator.run.return_value = mock_result
        session._orchestrator = mock_orchestrator

        session.process_text("hello")
        call_kwargs = mock_orchestrator.run.call_args
        extra_system = call_kwargs.kwargs.get("extra_system", "")
        assert extra_system == ""


class TestStreamExtraSystem:
    """验证 process_text_stream 也正确传递 extra_system"""

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="group_hint")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="skill_hint")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_stream_passes_extra_system(self, mock_init, mock_skill, mock_group):
        session = VoiceSession()
        session._initialized = True

        from voice_assistant.agent.orchestrator import AgentResult

        def fake_stream(*args, **kwargs):
            yield MagicMock(type="complete", result=AgentResult(
                success=True, response="streamed", tool_calls_made=[],
            ))

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_stream = fake_stream
        session._orchestrator = mock_orchestrator

        # We can't easily inspect run_stream kwargs since it's a generator,
        # but we can verify _build_skill_addendum and _build_tool_group_hint were called
        list(session.process_text_stream("hello"))
        mock_skill.assert_called_once_with("hello")
        mock_group.assert_called_once()


class TestBuildToolGroupHint:
    """测试 _build_tool_group_hint 函数"""

    def test_returns_string(self):
        result = _build_tool_group_hint()
        assert isinstance(result, str)

    def test_includes_group_names(self):
        result = _build_tool_group_hint()
        # Should mention at least the core group
        if result:  # May be empty if tool_groups is empty
            assert "core" in result.lower() or "工具" in result or "tool" in result.lower()


class TestSessionHistoryTrimmingWithProcessText:
    """测试 process_text 后历史裁剪"""

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_process_text_appends_and_trims_history(self, mock_init, mock_skill, mock_group):
        session = VoiceSession()
        session._initialized = True
        session._max_history_turns = 4
        session._max_context_tokens = 1_000_000

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "reply"
        mock_result.tool_calls_made = []
        mock_orchestrator.run.return_value = mock_result
        session._orchestrator = mock_orchestrator

        # Process multiple turns
        for i in range(10):
            session.process_text(f"msg {i}")

        # History should be trimmed
        assert len(session._history) <= 4

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_process_text_history_contains_user_and_assistant(self, mock_init, mock_skill, mock_group):
        session = VoiceSession()
        session._initialized = True

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "hello reply"
        mock_result.tool_calls_made = []
        mock_orchestrator.run.return_value = mock_result
        session._orchestrator = mock_orchestrator

        session.process_text("hello")
        assert len(session._history) == 2
        assert session._history[0]["role"] == "user"
        assert session._history[0]["content"] == "hello"
        assert session._history[1]["role"] == "assistant"
        assert session._history[1]["content"] == "hello reply"


class TestProcessTextErrorHandling:
    """测试 process_text 错误处理"""

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_orchestrator_exception_returns_error_result(self, mock_init, mock_skill, mock_group):
        session = VoiceSession()
        session._initialized = True

        mock_orchestrator = MagicMock()
        mock_orchestrator.run.side_effect = RuntimeError("LLM down")
        session._orchestrator = mock_orchestrator

        result = session.process_text("hello")
        assert result.intent_type == "error"
        assert "LLM down" in result.response

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="")
    def test_empty_input_returns_unknown(self, mock_skill, mock_group):
        session = VoiceSession()
        session._initialized = True

        result = session.process_text("  ")
        assert result.intent_type == "unknown"
        assert result.confidence == 0.0


class TestExecutionCallbacks:
    """测试 on_execution_start/end 回调"""

    @patch("voice_assistant.core.session._build_tool_group_hint", return_value="")
    @patch("voice_assistant.core.session._build_skill_addendum", return_value="")
    @patch("voice_assistant.core.session.VoiceSession._ensure_initialized")
    def test_execution_callbacks_called(self, mock_init, mock_skill, mock_group):
        start_called = []
        end_called = []

        session = VoiceSession(
            on_execution_start=lambda: start_called.append(True),
            on_execution_end=lambda: end_called.append(True),
        )
        session._initialized = True

        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "done"
        mock_result.tool_calls_made = []
        mock_orchestrator.run.return_value = mock_result
        session._orchestrator = mock_orchestrator

        session.process_text("hello")
        assert len(start_called) == 1
        assert len(end_called) == 1
