"""TTS Provider 协议与工厂测试"""
from unittest.mock import MagicMock

import pytest

from voice_assistant.audio.tts import (
    _TTS_REGISTRY,
    EdgeTTSProvider,
    TTSProvider,
    create_tts_provider,
    preprocess_text,
    register_tts_provider,
)

# ---------------------------------------------------------------------------
# TTSProvider 协议一致性
# ---------------------------------------------------------------------------

class TestTTSProviderProtocol:
    """验证所有 TTSProvider 实现满足协议"""

    def test_edge_tts_satisfies_protocol(self):
        assert isinstance(EdgeTTSProvider(), TTSProvider)

    def test_custom_provider_satisfies_protocol(self):
        class DummyProvider:
            def synthesize(self, text: str, output_file: str) -> bool:
                return True
            def synthesize_to_bytes(self, text: str):
                return b"audio"
            def synthesize_stream(self, text: str):
                yield b"audio_chunk"
            def close(self) -> None:
                pass

        assert isinstance(DummyProvider(), TTSProvider)

    def test_incomplete_provider_fails_protocol(self):
        class IncompleteProvider:
            def synthesize(self, text: str, output_file: str) -> bool:
                return True

        assert not isinstance(IncompleteProvider(), TTSProvider)


# ---------------------------------------------------------------------------
# EdgeTTSProvider
# ---------------------------------------------------------------------------

class TestEdgeTTSProvider:

    def test_default_voice(self):
        provider = EdgeTTSProvider()
        assert provider.voice == "zh-CN-XiaoxiaoNeural"

    def test_custom_voice(self):
        provider = EdgeTTSProvider(voice="en-US-JennyNeural")
        assert provider.voice == "en-US-JennyNeural"

    def test_build_communicate_kwargs_empty_rate_pitch(self):
        provider = EdgeTTSProvider(voice="zh-CN-XiaoxiaoNeural", rate="", pitch="")
        kwargs = provider._build_communicate_kwargs()
        assert "voice" in kwargs
        assert "rate" not in kwargs
        assert "pitch" not in kwargs

    def test_build_communicate_kwargs_with_rate_pitch(self):
        provider = EdgeTTSProvider(rate="+10%", pitch="-5Hz")
        kwargs = provider._build_communicate_kwargs()
        assert kwargs["rate"] == "+10%"
        assert kwargs["pitch"] == "-5Hz"

    def test_close_cleans_loop(self):
        provider = EdgeTTSProvider()
        provider.close()
        assert provider._loop is None

    def test_close_idempotent(self):
        provider = EdgeTTSProvider()
        provider.close()
        provider.close()


# ---------------------------------------------------------------------------
# TTS 注册表与工厂
# ---------------------------------------------------------------------------

class TestTTSRegistry:

    def test_edge_tts_registered_by_default(self):
        assert "edge-tts" in _TTS_REGISTRY

    def test_register_custom_provider(self):
        class TestProvider:
            def synthesize(self, text, output_file): return True
            def synthesize_to_bytes(self, text): return None
            def close(self): pass

        register_tts_provider("test-custom", TestProvider)
        assert "test-custom" in _TTS_REGISTRY
        del _TTS_REGISTRY["test-custom"]

    def test_register_non_class_raises(self):
        with pytest.raises(TypeError):
            register_tts_provider("bad", "not_a_class")

    def test_register_duplicate_warns(self, caplog):
        class DupProvider:
            def synthesize(self, text, output_file): return True
            def synthesize_to_bytes(self, text): return None
            def close(self): pass

        register_tts_provider("dup-test", DupProvider)
        with caplog.at_level("WARNING"):
            register_tts_provider("dup-test", DupProvider)
        assert "已存在" in caplog.text or "覆盖" in caplog.text
        del _TTS_REGISTRY["dup-test"]


class TestCreateTTSProvider:

    def _make_config(self, provider="edge-tts", voice="zh-CN-XiaoxiaoNeural",
                     rate="", pitch=""):
        from voice_assistant.config import TTSConfig
        mock_config = MagicMock()
        mock_config.tts = TTSConfig(provider=provider, voice=voice, rate=rate, pitch=pitch)
        mock_config.audio = MagicMock()
        mock_config.audio.edge_tts_voice = voice
        return mock_config

    def test_create_edge_tts(self):
        config = self._make_config()
        provider = create_tts_provider(config)
        assert isinstance(provider, EdgeTTSProvider)
        assert provider.voice == "zh-CN-XiaoxiaoNeural"

    def test_create_with_rate_pitch(self):
        config = self._make_config(rate="+10%", pitch="-5Hz")
        provider = create_tts_provider(config)
        assert provider.rate == "+10%"
        assert provider.pitch == "-5Hz"

    def test_unknown_provider_raises(self):
        config = self._make_config(provider="nonexistent")
        with pytest.raises(ValueError, match="未知的 TTS 提供者"):
            create_tts_provider(config)

    def test_fallback_to_audio_config(self):
        mock_config = MagicMock()
        mock_config.tts = None
        mock_config.audio = MagicMock()
        mock_config.audio.edge_tts_voice = "en-US-JennyNeural"
        provider = create_tts_provider(mock_config)
        assert provider.voice == "en-US-JennyNeural"


# ---------------------------------------------------------------------------
# preprocess_text
# ---------------------------------------------------------------------------

class TestPreprocessText:

    def test_adds_pause_after_sentence(self):
        result = preprocess_text("你好。再见")
        assert "。 " in result

    def test_adds_space_after_comma(self):
        result = preprocess_text("你好，世界")
        assert "， " in result

    def test_collapse_multiple_spaces(self):
        result = preprocess_text("你好   世界")
        assert result == "你好 世界"
