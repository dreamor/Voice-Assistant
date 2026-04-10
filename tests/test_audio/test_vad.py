"""VAD 模块测试"""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock


class TestCalculateRMS:
    """测试 RMS 计算"""

    def test_rms_normal_audio(self):
        """测试正常音频的 RMS 计算"""
        from voice_assistant.audio.vad import calculate_rms

        # 生成正弦波音频
        sample_rate = 16000
        duration = 1
        t = np.linspace(0, duration, sample_rate * duration)
        audio_data = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

        rms = calculate_rms(audio_data)
        # numpy 返回 numpy.floating 类型
        assert isinstance(rms, (float, np.floating))
        assert rms > 0

    def test_rms_silence(self):
        """测试静音的 RMS"""
        from voice_assistant.audio.vad import calculate_rms

        # 静音（接近零）
        audio_data = np.zeros(16000, dtype=np.float32)
        rms = calculate_rms(audio_data)
        assert rms < 0.001

    def test_rms_empty_audio(self):
        """测试空音频数组的 RMS"""
        from voice_assistant.audio.vad import calculate_rms

        audio_data = np.array([], dtype=np.float32)
        rms = calculate_rms(audio_data)
        assert rms == 0.0

    def test_rms_constant_signal(self):
        """测试恒定信号的 RMS"""
        from voice_assistant.audio.vad import calculate_rms

        # 恒定值 0.5
        audio_data = np.full(16000, 0.5, dtype=np.float32)
        rms = calculate_rms(audio_data)
        assert abs(rms - 0.5) < 0.001

    def test_rms_negative_values(self):
        """测试负值音频的 RMS"""
        from voice_assistant.audio.vad import calculate_rms

        # 交替正负值
        audio_data = np.array([0.5, -0.5, 0.5, -0.5] * 4000, dtype=np.float32)
        rms = calculate_rms(audio_data)
        assert abs(rms - 0.5) < 0.001


class TestRecordAudio:
    """测试 VAD 录音功能"""

    @patch('voice_assistant.audio.vad.sd.InputStream')
    @patch('voice_assistant.audio.vad.config')
    def test_record_audio_timeout_waiting_for_voice(self, mock_config, mock_stream_class):
        """测试等待语音超时"""
        from voice_assistant.audio.vad import record_audio

        # 配置 mock
        mock_vad_cfg = MagicMock()
        mock_vad_cfg.threshold = 0.01
        mock_vad_cfg.wait_timeout = 0.1
        mock_vad_cfg.silence_timeout = 1.0
        mock_vad_cfg.max_recording = 10.0
        mock_vad_cfg.min_speech = 0.3

        mock_audio_cfg = MagicMock()
        mock_audio_cfg.sample_rate = 16000

        mock_config.vad = mock_vad_cfg
        mock_config.audio = mock_audio_cfg

        # 模拟流
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream

        result = record_audio(max_seconds=1.0)

        # 超时后应返回空数组
        assert isinstance(result, np.ndarray)
        assert len(result) == 0

    @patch('voice_assistant.audio.vad.sd.InputStream')
    @patch('voice_assistant.audio.vad.config')
    def test_record_audio_returns_array(self, mock_config, mock_stream_class):
        """测试 record_audio 返回数组类型"""
        from voice_assistant.audio.vad import record_audio

        # 配置 mock
        mock_vad_cfg = MagicMock()
        mock_vad_cfg.threshold = 0.01
        mock_vad_cfg.wait_timeout = 0.01  # 快速超时
        mock_vad_cfg.silence_timeout = 0.1
        mock_vad_cfg.max_recording = 1.0
        mock_vad_cfg.min_speech = 0.1

        mock_audio_cfg = MagicMock()
        mock_audio_cfg.sample_rate = 16000

        mock_config.vad = mock_vad_cfg
        mock_config.audio = mock_audio_cfg

        # 模拟流
        mock_stream = MagicMock()
        mock_stream_class.return_value = mock_stream

        # 测试函数返回类型
        result = record_audio(max_seconds=0.1)
        assert isinstance(result, np.ndarray)


class TestVADIntegration:
    """VAD 集成测试"""

    def test_vad_module_imports(self):
        """测试模块导入"""
        from voice_assistant.audio.vad import calculate_rms, record_audio
        assert calculate_rms is not None
        assert record_audio is not None

    def test_rms_with_different_sample_rates(self):
        """测试不同采样率的 RMS 计算"""
        from voice_assistant.audio.vad import calculate_rms

        for sample_rate in [8000, 16000, 44100, 48000]:
            duration = 0.1
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

            rms = calculate_rms(audio)
            assert 0 < rms < 1.0, f"RMS out of range for sample rate {sample_rate}"