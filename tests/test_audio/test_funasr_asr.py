"""Integration tests for FunASR local ASR module."""
import os
import struct
import tempfile
import wave

import pytest
from unittest.mock import MagicMock, patch


class TestFunASREngineIntegration:
    """Test FunASREngine with mocked AutoModel"""

    @pytest.fixture
    def sample_wav_path(self):
        """Create a sample WAV file"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        sample_rate = 16000
        n_samples = int(sample_rate * 1.0)
        with wave.open(tmp_path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            for _ in range(n_samples):
                wf.writeframes(struct.pack('<h', 0))

        yield tmp_path
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    @patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True)
    @patch('voice_assistant.audio.funasr_asr.AutoModel')
    def test_recognize_from_file(self, mock_automodel, sample_wav_path):
        """Test recognition from file"""
        from voice_assistant.audio.funasr_asr import FunASREngine

        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "\u4f60\u597d\u4e16\u754c"}]
        mock_automodel.return_value = mock_model

        engine = FunASREngine()
        result = engine.recognize(sample_wav_path)

        assert result == "\u4f60\u597d\u4e16\u754c"
        mock_model.generate.assert_called_once()

    @patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True)
    @patch('voice_assistant.audio.funasr_asr.AutoModel')
    def test_recognize_with_hotwords(self, mock_automodel, sample_wav_path):
        """Test recognition with hotwords"""
        from voice_assistant.audio.funasr_asr import FunASREngine

        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "Python\u7f16\u7a0b"}]
        mock_automodel.return_value = mock_model

        engine = FunASREngine()
        result = engine.recognize(sample_wav_path, hotwords=["Python", "\u7f16\u7a0b"])

        assert result == "Python\u7f16\u7a0b"
        call_kwargs = mock_model.generate.call_args.kwargs
        assert "hotword" in call_kwargs

    @patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True)
    @patch('voice_assistant.audio.funasr_asr.AutoModel')
    def test_recognize_empty_result(self, mock_automodel, sample_wav_path):
        """Test recognition returns empty string for empty result"""
        from voice_assistant.audio.funasr_asr import FunASREngine

        mock_model = MagicMock()
        mock_model.generate.return_value = []
        mock_automodel.return_value = mock_model

        engine = FunASREngine()
        result = engine.recognize(sample_wav_path)

        assert result == ""

    @patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True)
    @patch('voice_assistant.audio.funasr_asr.AutoModel')
    def test_recognize_bytes_wav(self, mock_automodel):
        """Test recognition from WAV bytes"""
        from voice_assistant.audio.funasr_asr import FunASREngine

        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "\u6d4b\u8bd5"}]
        mock_automodel.return_value = mock_model

        # Create WAV bytes
        sample_rate = 16000
        n_samples = int(sample_rate * 0.5)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            with wave.open(tmp.name, 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                for _ in range(n_samples):
                    wf.writeframes(struct.pack('<h', 0))
            with open(tmp.name, 'rb') as f:
                wav_bytes = f.read()
            os.unlink(tmp.name)

        engine = FunASREngine()
        result = engine.recognize_bytes(wav_bytes, sample_rate=sample_rate)

        assert result == "\u6d4b\u8bd5"


class TestFunASRClientIntegration:
    """Test FunASRClient with mocked engine"""

    @patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True)
    @patch('voice_assistant.audio.funasr_asr.AutoModel')
    def test_client_recognize(self, mock_automodel):
        """Test client recognize method"""
        from voice_assistant.audio.funasr_asr import FunASRClient

        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "\u5ba2\u6237\u7aef\u6d4b\u8bd5"}]
        mock_automodel.return_value = mock_model

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            client = FunASRClient()
            result = client.recognize(tmp_path)
            assert result == "\u5ba2\u6237\u7aef\u6d4b\u8bd5"
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True)
    @patch('voice_assistant.audio.funasr_asr.AutoModel')
    def test_client_close(self, mock_automodel):
        """Test client close releases resources"""
        from voice_assistant.audio.funasr_asr import FunASRClient

        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "test"}]
        mock_automodel.return_value = mock_model

        client = FunASRClient()
        client._ensure_engine()
        assert client._engine is not None

        client.close()
        assert client._engine is None
