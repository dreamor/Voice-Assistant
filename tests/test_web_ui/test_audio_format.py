"""Web UI 音频格式转换测试"""
import io
import wave
from unittest import mock

import pytest


def _make_wav_bytes(sample_rate: int = 16000, channels: int = 1,
                    duration: float = 0.1) -> bytes:
    """生成合成的 WAV 字节数据"""
    buf = io.BytesIO()
    n_samples = int(sample_rate * duration)
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = (b"\x00\x00" * n_samples) * channels
        w.writeframes(frames)
    return buf.getvalue()


class TestConvertAudioToWav:
    """测试 _convert_audio_to_wav 函数"""

    @pytest.fixture(autouse=True)
    def _import_func(self):
        from web_ui import _convert_audio_to_wav
        self.convert = _convert_audio_to_wav

    def test_wav_passthrough(self):
        """WAV 格式直接返回有效 WAV"""
        wav_16k = _make_wav_bytes(sample_rate=16000)
        result = self.convert(wav_16k, "audio/wav")
        with wave.open(io.BytesIO(result), "rb") as w:
            assert w.getnchannels() == 1
            assert w.getframerate() == 16000

    def test_wav_resample_44k_to_16k(self):
        """44.1kHz WAV 重采样到 16kHz"""
        wav_44k = _make_wav_bytes(sample_rate=44100)
        result = self.convert(wav_44k, "audio/wav")
        with wave.open(io.BytesIO(result), "rb") as w:
            assert w.getframerate() == 16000
            assert w.getnchannels() == 1

    def test_stereo_to_mono(self):
        """立体声 WAV 转单声道"""
        wav_stereo = _make_wav_bytes(sample_rate=16000, channels=2)
        result = self.convert(wav_stereo, "audio/wav")
        with wave.open(io.BytesIO(result), "rb") as w:
            assert w.getnchannels() == 1

    def test_webm_format_fallback_on_invalid_data(self):
        """WebM 格式无效数据时返回原始数据"""
        result = self.convert(b"not_real_webm_data", "audio/webm")
        assert result == b"not_real_webm_data"

    def test_ogg_format_fallback_on_invalid_data(self):
        """OGG 格式无效数据时返回原始数据"""
        result = self.convert(b"not_real_ogg_data", "audio/ogg")
        assert result == b"not_real_ogg_data"

    def test_empty_wav(self):
        """短 WAV 数据处理"""
        wav_short = _make_wav_bytes(sample_rate=16000, duration=0.01)
        result = self.convert(wav_short, "audio/wav")
        with wave.open(io.BytesIO(result), "rb") as w:
            assert w.getframerate() == 16000

    def test_wav_format_independent_of_pydub(self):
        """WAV 格式不依赖 pydub，soundfile 处理"""
        wav = _make_wav_bytes()
        result = self.convert(wav, "audio/wav")
        with wave.open(io.BytesIO(result), "rb") as w:
            assert w.getframerate() == 16000