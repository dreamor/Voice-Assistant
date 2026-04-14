"""Tests for FunASR local ASR module."""
import os
import struct
import tempfile
import wave

import pytest
from unittest.mock import patch


class TestFunASRConfig:
    """Test FunASR config dataclasses"""

    def test_local_asr_config_defaults(self):
        """Test LocalASRConfig default values"""
        from voice_assistant.config import LocalASRConfig
        cfg = LocalASRConfig(
            enabled=False,
            model_path=None,
            device="cpu",
            vad_threshold=0.5,
        )
        assert cfg.enabled is False
        assert cfg.model_path is None
        assert cfg.device == "cpu"
        assert cfg.vad_threshold == 0.5

    def test_asr_config_has_use_local(self):
        """Test ASRConfig has use_local field"""
        from voice_assistant.config import ASRConfig, HotwordsConfig, LocalASRConfig
        local_cfg = LocalASRConfig(enabled=False, model_path=None, device="cpu", vad_threshold=0.5)
        hotwords = HotwordsConfig(enabled=False, config_file="config/hotwords.json", vocabulary_id=None)
        cfg = ASRConfig(
            model="paraformer-realtime-v2",
            base_url="https://dashscope.aliyuncs.com/api/v1",
            api_key="test",
            language_hints=["zh", "en"],
            disfluency_removal_enabled=True,
            max_sentence_silence=1200,
            hotwords=hotwords,
            use_local=True,
            local=local_cfg,
        )
        assert cfg.use_local is True


class TestFunASREngine:
    """Test FunASREngine class"""

    def test_engine_raises_when_funasr_not_installed(self):
        """Test engine raises FunASRError when FunASR not available"""
        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', False):
            from voice_assistant.audio.funasr_asr import FunASREngine, FunASRError

            with pytest.raises(FunASRError, match="FunASR 未安装"):
                FunASREngine()

    def test_engine_init_with_defaults(self):
        """Test engine can be patched to init"""
        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', False):
            from voice_assistant.audio.funasr_asr import FunASREngine, FunASRError

            with pytest.raises(FunASRError):
                FunASREngine(device="cpu")

                engine = FunASREngine(device="cpu")
                assert engine.device == "cpu"

class TestFunASRClient:
    """Test FunASRClient class"""

    def test_client_init(self):
        """Test client initialization"""
        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', False):
            from voice_assistant.audio.funasr_asr import FunASRClient

            client = FunASRClient()
            assert client._engine is None
            assert client.device == "cpu"

    def test_client_ensure_engine_raises_when_not_available(self):
        """Test _ensure_engine raises when FunASR not available"""
        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', False):
            from voice_assistant.audio.funasr_asr import FunASRClient, FunASRError

            client = FunASRClient()
            with pytest.raises(FunASRError):
                client._ensure_engine()


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

        try:
            os.unlink(tmp_path)
        except OSError:
            pass

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

    def test_config_loads_asr_use_local(self):
        """Test that config loads asr.use_local from yaml"""
        from voice_assistant.config import load_config

        config = load_config()

        # Should have the attribute
        assert hasattr(config.asr, 'use_local')
        assert isinstance(config.asr.use_local, bool)

    def test_config_loads_asr_local(self):
        """Test that config loads asr.local section"""
        from voice_assistant.config import load_config

        config = load_config()

        assert hasattr(config.asr, 'local')
        assert hasattr(config.asr.local, 'enabled')
        assert hasattr(config.asr.local, 'device')
        assert hasattr(config.asr.local, 'vad_threshold')
