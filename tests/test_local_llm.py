"""Tests for local LLM module and multimodal audio functionality."""
import os
import tempfile
import wave
import struct
import pytest
from unittest.mock import patch


class TestLocalLLMConfig:
    """Test LocalLLMConfig from config module"""

    def test_use_multimodal_audio_default(self):
        """Test that use_multimodal_audio defaults to False"""
        from voice_assistant.config import LocalLLMConfig
        config = LocalLLMConfig(
            model_path="models/test.litertlm",
            model_name="test-model",
            system_prompt="Test prompt"
        )
        assert config.use_multimodal_audio is False

    def test_use_multimodal_audio_enabled(self):
        """Test that use_multimodal_audio can be enabled"""
        from voice_assistant.config import LocalLLMConfig
        config = LocalLLMConfig(
            model_path="models/test.litertlm",
            model_name="test-model",
            system_prompt="Test prompt",
            use_multimodal_audio=True
        )
        assert config.use_multimodal_audio is True


class TestLocalLLMEngineMultimodal:
    """Test LocalLLMEngine multimodal audio support"""

    def test_engine_init_with_audio_disabled(self):
        """Test engine initialization without audio"""
        with patch('voice_assistant.core.local_llm.LITERT_LM_AVAILABLE', False):
            from voice_assistant.core.local_llm import LocalLLMEngine, LocalLLMError

            # Should raise error when litert_lm not available
            with pytest.raises(LocalLLMError, match="LiteRT-LM 未安装"):
                LocalLLMEngine("nonexistent.litertlm", enable_audio=False)

    def test_engine_init_with_audio_enabled(self):
        """Test engine initialization with audio flag"""
        with patch('voice_assistant.core.local_llm.LITERT_LM_AVAILABLE', False):
            from voice_assistant.core.local_llm import LocalLLMEngine, LocalLLMError

            # Should raise error when litert_lm not available
            with pytest.raises(LocalLLMError, match="LiteRT-LM 未安装"):
                LocalLLMEngine("nonexistent.litertlm", enable_audio=True)


class TestLocalLLMClientMultimodal:
    """Test LocalLLMClient multimodal audio support"""

    def test_client_init_audio_disabled(self):
        """Test client initialization without audio"""
        with patch('voice_assistant.core.local_llm.LITERT_LM_AVAILABLE', False):
            from voice_assistant.core.local_llm import LocalLLMClient

            client = LocalLLMClient(
                model_path="models/test.litertlm",
                enable_audio=False
            )
            assert client.enable_audio is False
            assert client._engine is None

    def test_client_init_audio_enabled(self):
        """Test client initialization with audio flag"""
        with patch('voice_assistant.core.local_llm.LITERT_LM_AVAILABLE', False):
            from voice_assistant.core.local_llm import LocalLLMClient

            client = LocalLLMClient(
                model_path="models/test.litertlm",
                enable_audio=True
            )
            assert client.enable_audio is True
            assert client._engine is None

    def test_ask_multimodal_stream_without_engine(self):
        """Test multimodal stream without engine raises error"""
        with patch('voice_assistant.core.local_llm.LITERT_LM_AVAILABLE', False):
            from voice_assistant.core.local_llm import LocalLLMClient

            client = LocalLLMClient(
                model_path="models/test.litertlm",
                enable_audio=True
            )

            # Create a dummy WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                # Should yield error message when engine fails to initialize
                results = list(client.ask_multimodal_stream("test", tmp_path))
                assert len(results) > 0
                assert "抱歉" in results[0] or "错误" in results[0]
            finally:
                os.unlink(tmp_path)


class TestAIClientMultimodal:
    """Test AI client multimodal audio support"""

    def test_ask_ai_stream_with_audio_signature(self):
        """Test ask_ai_stream_with_audio function exists"""
        from voice_assistant.core.ai_client import ask_ai_stream_with_audio
        import inspect

        sig = inspect.signature(ask_ai_stream_with_audio)
        params = list(sig.parameters.keys())

        assert 'text' in params
        assert 'wav_file_path' in params
        assert 'conversation_history' in params

    def test_ask_ai_stream_with_audio_local_unavailable(self):
        """Test multimodal audio when local LLM is unavailable"""
        with patch('voice_assistant.core.ai_client.get_local_llm_client') as mock_get:
            mock_get.return_value = None

            from voice_assistant.core.ai_client import ask_ai_stream_with_audio

            results = list(ask_ai_stream_with_audio("test", "/tmp/test.wav"))
            assert len(results) > 0
            assert "不可用" in results[0] or "LiteRT" in results[0]


class TestWAVFileHandling:
    """Test WAV file handling for multimodal audio"""

    @pytest.fixture
    def sample_wav(self):
        """Create a sample WAV file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        # Create a simple WAV file with silence
        sample_rate = 16000
        duration = 1.0
        n_samples = int(sample_rate * duration)

        with wave.open(tmp_path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            for _ in range(n_samples):
                wf.writeframes(struct.pack('<h', 0))

        yield tmp_path

        os.unlink(tmp_path)

    def test_wav_file_creation(self, sample_wav):
        """Test that WAV file is created correctly"""
        assert os.path.exists(sample_wav)

        with wave.open(sample_wav, 'r') as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000

    def test_wav_file_size(self, sample_wav):
        """Test WAV file size is reasonable"""
        size = os.path.getsize(sample_wav)
        # 1 second of 16kHz 16-bit mono audio should be ~32KB + header
        assert 30000 < size < 40000


class TestConfigLoading:
    """Test config loading with multimodal audio settings"""

    def test_config_loads_multimodal_setting(self):
        """Test that config loads use_multimodal_audio from yaml"""
        from voice_assistant.config import load_config

        config = load_config()

        # Should have the attribute
        assert hasattr(config.llm.local, 'use_multimodal_audio')
        # Should be a boolean
        assert isinstance(config.llm.local.use_multimodal_audio, bool)