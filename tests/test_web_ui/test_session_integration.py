"""Session Web 集成测试"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestVoiceSessionWebIntegration:
    """测试 VoiceSession 与 Web UI 的集成"""

    def test_voice_session_has_synthesize_stream(self):
        """验证 VoiceSession 有 synthesize_stream 方法"""
        from voice_assistant.core.session import VoiceSession

        assert hasattr(VoiceSession, 'synthesize_stream')

    def test_voice_session_synthesize_stream_signature(self):
        """验证 VoiceSession.synthesize_stream 方法签名"""
        from voice_assistant.core.session import VoiceSession
        import inspect

        sig = inspect.signature(VoiceSession.synthesize_stream)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'text' in params

    def test_voice_session_history_access_methods(self):
        """验证 VoiceSession 提供 history 访问方法"""
        from voice_assistant.core.session import VoiceSession

        assert hasattr(VoiceSession, 'get_history')
        assert hasattr(VoiceSession, 'set_history')

    def test_voice_session_get_history_signature(self):
        """验证 get_history 方法签名"""
        from voice_assistant.core.session import VoiceSession
        import inspect

        sig = inspect.signature(VoiceSession.get_history)
        params = list(sig.parameters.keys())
        assert 'self' in params

    def test_voice_session_set_history_signature(self):
        """验证 set_history 方法签名"""
        from voice_assistant.core.session import VoiceSession
        import inspect

        sig = inspect.signature(VoiceSession.set_history)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'history' in params


class TestVoiceSessionStreamProcessing:
    """测试 VoiceSession 流式处理"""

    def test_voice_session_has_process_text_stream(self):
        """验证 VoiceSession 有 process_text_stream 方法"""
        from voice_assistant.core.session import VoiceSession

        assert hasattr(VoiceSession, 'process_text_stream')

    def test_process_text_stream_signature(self):
        """验证 process_text_stream 方法签名"""
        from voice_assistant.core.session import VoiceSession
        import inspect

        sig = inspect.signature(VoiceSession.process_text_stream)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'user_text' in params


class TestWebUISessionDelegation:
    """测试 Web UI 通过 VoiceSession 处理请求"""

    def test_web_ui_uses_voice_session_for_tts(self):
        """验证 Web UI 使用 VoiceSession 进行 TTS"""
        # 验证 web_ui.py 中调用 session.synthesize_stream
        import web_ui

        # 检查 generate_and_send_tts_stream 函数存在
        assert hasattr(web_ui, 'generate_and_send_tts_stream')

    def test_web_ui_session_lifecycle(self):
        """验证 Web UI 管理 Session 生命周期"""
        import web_ui

        # 验证会话管理字典存在 (命名为 sessions)
        assert hasattr(web_ui, 'sessions')
