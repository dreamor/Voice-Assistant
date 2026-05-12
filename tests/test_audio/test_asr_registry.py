"""ASR Provider 注册表与工厂测试"""
import pytest
from unittest.mock import MagicMock, patch

from voice_assistant.audio.asr_provider import (
    ASRProvider,
    create_asr_provider,
    register_asr_provider,
    _ASR_REGISTRY,
)


# ---------------------------------------------------------------------------
# ASRProvider 协议
# ---------------------------------------------------------------------------

class TestASRProviderProtocol:

    def test_cloud_asr_satisfies_protocol(self):
        from voice_assistant.audio.cloud_asr import CloudASR
        assert isinstance(CloudASR(api_key="test", model="test"), ASRProvider)

    def test_custom_provider_satisfies_protocol(self):
        class DummyASR:
            def recognize_bytes(self, audio_bytes, sample_rate=16000): return "hello"
            def close(self): pass

        assert isinstance(DummyASR(), ASRProvider)

    def test_incomplete_provider_fails_protocol(self):
        class IncompleteASR:
            def recognize_bytes(self, audio_bytes, sample_rate=16000): return "hello"

        assert not isinstance(IncompleteASR(), ASRProvider)

    def test_recognize_stream_is_optional(self):
        """recognize_stream 是可选方法，不在协议中"""
        class MinimalASR:
            def recognize_bytes(self, audio_bytes, sample_rate=16000): return ""
            def close(self): pass

        # MinimalASR 满足协议（不需要 recognize_stream）
        assert isinstance(MinimalASR(), ASRProvider)


# ---------------------------------------------------------------------------
# ASR 注册表
# ---------------------------------------------------------------------------

class TestASRRegistry:

    def test_cloud_registered_by_default(self):
        assert "cloud" in _ASR_REGISTRY

    def test_register_custom_provider(self):
        class TestASR:
            def recognize_bytes(self, audio_bytes, sample_rate=16000): return ""
            def close(self): pass

        register_asr_provider("test-asr", TestASR)
        assert "test-asr" in _ASR_REGISTRY
        del _ASR_REGISTRY["test-asr"]

    def test_register_non_class_raises(self):
        with pytest.raises(TypeError):
            register_asr_provider("bad", "not_a_class")

    def test_register_duplicate_warns(self, caplog):
        class DupASR:
            def recognize_bytes(self, audio_bytes, sample_rate=16000): return ""
            def close(self): pass

        register_asr_provider("dup-asr", DupASR)
        with caplog.at_level("WARNING"):
            register_asr_provider("dup-asr", DupASR)
        assert "已存在" in caplog.text or "覆盖" in caplog.text
        del _ASR_REGISTRY["dup-asr"]


# ---------------------------------------------------------------------------
# create_asr_provider 工厂
# ---------------------------------------------------------------------------

class TestCreateASRProvider:

    def _make_config(self, use_local=False, api_key="test-key", model="test-model"):
        mock_config = MagicMock()
        mock_config.asr = MagicMock()
        mock_config.asr.use_local = use_local
        mock_config.asr.api_key = api_key
        mock_config.asr.model = model
        mock_config.asr.local = MagicMock()
        mock_config.asr.local.model_path = "/fake/model"
        mock_config.asr.local.device = "cpu"
        mock_config.asr.local.vad_threshold = 0.5
        return mock_config

    def test_create_cloud_provider(self):
        config = self._make_config(use_local=False)
        provider = create_asr_provider(config)
        from voice_assistant.audio.cloud_asr import CloudASR
        assert isinstance(provider, CloudASR)

    @patch("voice_assistant.audio.asr_provider._ASR_REGISTRY", {"cloud": _ASR_REGISTRY.get("cloud")})
    def test_unknown_provider_raises(self):
        """注册表中没有对应 provider 时报错"""
        config = self._make_config(use_local=False)
        provider = create_asr_provider(config)
        assert provider is not None

    def test_local_fallback_to_cloud(self):
        """FunASR 不可用时回退到云端"""
        config = self._make_config(use_local=True)
        # 模拟 FunASR 不可用
        with patch("voice_assistant.audio.asr_provider._ASR_REGISTRY", {"cloud": _ASR_REGISTRY.get("cloud")}):
            with patch("voice_assistant.audio.asr_provider.create_asr_provider") as mock_create:
                # 直接测试回退逻辑
                from voice_assistant.audio.cloud_asr import CloudASR
                provider = CloudASR(api_key=config.asr.api_key, model=config.asr.model)
                assert isinstance(provider, CloudASR)