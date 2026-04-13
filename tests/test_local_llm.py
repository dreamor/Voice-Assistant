"""Tests for FunASR local speech recognition module."""
import os
import tempfile
import wave
import struct
import pytest
from unittest.mock import patch, MagicMock


class TestFunASRConfig:
    """Test FunASR configuration"""

    def test_use_local_default(self):
        """Test that asr.use_local defaults to False"""
        from voice_assistant.config import ASRConfig, LocalASRConfig
        config = ASRConfig(
            api_key="test",
            model="paraformer",
            base_url="http://test",
            language_hints=["zh", "en"],
            disfluency_removal_enabled=False,
            max_sentence_silence=800,
            hotwords=MagicMock(),
            use_local=False,
            local=LocalASRConfig(enabled=False, model_path=None, device="cpu", vad_threshold=0.5)
        )
        assert config.use_local is False

    def test_use_local_enabled(self):
        """Test that asr.use_local can be enabled"""
        from voice_assistant.config import ASRConfig, LocalASRConfig
        local = LocalASRConfig(enabled=True, model_path="models/funasr", device="cpu", vad_threshold=0.5)
        config = ASRConfig(
            api_key="test",
            model="paraformer",
            base_url="http://test",
            language_hints=["zh", "en"],
            disfluency_removal_enabled=False,
            max_sentence_silence=800,
            hotwords=MagicMock(),
            use_local=True,
            local=local
        )
        assert config.use_local is True
        assert config.local.enabled is True
        assert config.local.device == "cpu"


class TestFunASREngine:
    """Test FunASR engine initialization and recognition"""

    def test_engine_init_cpu(self):
        """Test engine initialization on CPU"""
        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', False):
            from voice_assistant.audio.funasr_asr import FunASREngine, FunASRError

            # Should raise error when FunASR not available
            with pytest.raises(FunASRError, match="FunASR 未安装"):
                FunASREngine(device="cpu")

    def test_engine_init_device(self):
        """Test engine device setting"""
        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
            with patch('voice_assistant.audio.funasr_asr.AutoModel'):
                from voice_assistant.audio.funasr_asr import FunASREngine

                engine = FunASREngine(device="cpu")
                assert engine.device == "cpu"


class TestFunASRClient:
    """Test FunASR client interface"""

    def test_client_init(self):
        """Test client initialization"""
        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
            with patch('voice_assistant.audio.funasr_asr.FunASREngine'):
                from voice_assistant.audio.funasr_asr import FunASRClient

                client = FunASRClient(model_path="models/funasr", device="cpu")
                assert client is not None

    def test_client_recognize(self):
        """Test client recognize method"""
        mock_engine = MagicMock()
        mock_engine.recognize.return_value = "你好世界"

        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
            with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                from voice_assistant.audio.funasr_asr import FunASRClient

                client = FunASRClient(model_path="models/funasr", device="cpu")
                result = client.recognize("test.wav")
                assert result == "你好世界"
                mock_engine.recognize.assert_called_once_with("test.wav", hotwords=None)

    def test_client_recognize_with_hotwords(self):
        """Test client recognize with hotwords"""
        mock_engine = MagicMock()
        mock_engine.recognize.return_value = "阿里巴巴"

        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
            with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                from voice_assistant.audio.funasr_asr import FunASRClient

                client = FunASRClient(model_path="models/funasr", device="cpu")
                result = client.recognize("test.wav", hotwords="阿里巴巴 100")
                assert result == "阿里巴巴"
                mock_engine.recognize.assert_called_once_with("test.wav", hotwords="阿里巴巴 100")

    def test_client_recognize_bytes(self):
        """Test client recognize_bytes method"""
        mock_engine = MagicMock()
        mock_engine.recognize_bytes.return_value = "测试识别结果"

        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
            with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                from voice_assistant.audio.funasr_asr import FunASRClient

                client = FunASRClient(model_path="models/funasr", device="cpu")
                audio_bytes = b"fake wav data"
                result = client.recognize_bytes(audio_bytes, sample_rate=16000)
                assert result == "测试识别结果"
                mock_engine.recognize_bytes.assert_called_once()

    def test_client_close(self):
        """Test client close method"""
        mock_engine = MagicMock()

        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
            with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                from voice_assistant.audio.funasr_asr import FunASRClient

                client = FunASRClient(model_path="models/funasr", device="cpu")
                client.close()
                mock_engine.close.assert_called_once()


class TestWAVFileHandling:
    """Test WAV file handling for ASR"""

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
    """Test config loading with FunASR settings"""

    def test_config_loads_asr_setting(self):
        """Test that config loads asr.use_local from yaml"""
        from voice_assistant.config import load_config

        config = load_config()

        # Should have the attribute
        assert hasattr(config.asr, 'use_local')
        # Should be a boolean
        assert isinstance(config.asr.use_local, bool)

    def test_config_has_local_asr_config(self):
        """Test that config has local ASR configuration"""
        from voice_assistant.config import load_config

        config = load_config()

        assert hasattr(config.asr, 'local')
        assert hasattr(config.asr.local, 'device')
        assert hasattr(config.asr.local, 'vad_threshold')

    def test_config_no_longer_has_local_llm(self):
        """Test that config no longer has local LLM configuration"""
        from voice_assistant.config import load_config

        config = load_config()

        # LLM config should not have 'local' anymore
        assert not hasattr(config.llm, 'local') or config.llm.local is None
