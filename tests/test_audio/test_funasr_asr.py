"""Integration tests for FunASR audio recognition module."""
import os
import tempfile
import wave
import struct
import pytest
from unittest.mock import patch, MagicMock


class TestFunASRIntegration:
    """Test FunASR engine integration with mocked AutoModel"""

    def _create_silent_wav(self, duration=1.0, sample_rate=16000):
        """Create a silent WAV file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        n_samples = int(sample_rate * duration)
        with wave.open(tmp_path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            for _ in range(n_samples):
                wf.writeframes(struct.pack('<h', 0))

        return tmp_path

    def test_recognize_from_file(self):
        """Test recognizing from a WAV file"""
        wav_path = self._create_silent_wav()
        try:
            mock_engine = MagicMock()
            mock_engine.recognize.return_value = "你好世界"
            mock_engine.recognize_bytes.return_value = "你好世界"

            with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
                with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                    from voice_assistant.audio.funasr_asr import FunASRClient

                    client = FunASRClient(model_path="models/funasr", device="cpu")
                    result = client.recognize(wav_path)
                    assert result == "你好世界"
        finally:
            os.unlink(wav_path)

    def test_recognize_with_hotwords(self):
        """Test recognizing with hotwords"""
        wav_path = self._create_silent_wav()
        try:
            mock_engine = MagicMock()
            mock_engine.recognize.return_value = "阿里巴巴"
            mock_engine.recognize_bytes.return_value = "阿里巴巴"

            with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
                with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                    from voice_assistant.audio.funasr_asr import FunASRClient

                    client = FunASRClient(model_path="models/funasr", device="cpu")
                    result = client.recognize(wav_path, hotwords="阿里巴巴 100")
                    assert result == "阿里巴巴"
        finally:
            os.unlink(wav_path)

    def test_recognize_empty_result(self):
        """Test handling empty recognition result"""
        wav_path = self._create_silent_wav()
        try:
            mock_engine = MagicMock()
            mock_engine.recognize.return_value = ""
            mock_engine.recognize_bytes.return_value = ""

            with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
                with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                    from voice_assistant.audio.funasr_asr import FunASRClient

                    client = FunASRClient(model_path="models/funasr", device="cpu")
                    result = client.recognize(wav_path)
                    assert result == ""
        finally:
            os.unlink(wav_path)

    def test_recognize_bytes_wav(self):
        """Test recognizing WAV bytes directly"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        sample_rate = 16000
        duration = 1.0
        n_samples = int(sample_rate * duration)

        with wave.open(tmp_path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            for _ in range(n_samples):
                wf.writeframes(struct.pack('<h', 0))

        try:
            with open(tmp_path, 'rb') as f:
                audio_bytes = f.read()

            mock_engine = MagicMock()
            mock_engine.recognize.return_value = "测试"
            mock_engine.recognize_bytes.return_value = "测试"

            with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
                with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                    from voice_assistant.audio.funasr_asr import FunASRClient

                    client = FunASRClient(model_path="models/funasr", device="cpu")
                    result = client.recognize_bytes(audio_bytes, sample_rate=16000)
                    assert result == "测试"
        finally:
            os.unlink(tmp_path)

    def test_client_recognize(self):
        """Test client recognize method"""
        mock_engine = MagicMock()
        mock_engine.recognize.return_value = "你好"
        mock_engine.recognize_bytes.return_value = "你好"

        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
            with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                from voice_assistant.audio.funasr_asr import FunASRClient

                client = FunASRClient(model_path="models/funasr", device="cpu")
                result = client.recognize("test.wav")
                assert result == "你好"
                mock_engine.recognize.assert_called_once_with("test.wav", hotwords=None)

    def test_client_close(self):
        """Test client close method"""
        mock_engine = MagicMock()

        with patch('voice_assistant.audio.funasr_asr.FUNASR_AVAILABLE', True):
            with patch('voice_assistant.audio.funasr_asr.FunASREngine', return_value=mock_engine):
                from voice_assistant.audio.funasr_asr import FunASRClient

                client = FunASRClient(model_path="models/funasr", device="cpu")
                client.close()
                mock_engine.close.assert_called_once()
