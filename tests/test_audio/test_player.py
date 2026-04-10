"""Audio Player 模块测试"""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock


class TestPlayAudio:
    """测试音频播放功能"""

    @patch('voice_assistant.audio.player.pygame.mixer')
    @patch('voice_assistant.audio.player.os.unlink')
    def test_play_audio_basic(self, mock_unlink, mock_mixer):
        """测试基本音频播放"""
        from voice_assistant.audio.player import play_audio

        # 配置 mock
        mock_mixer.get_init.return_value = True
        mock_mixer.music.get_busy.side_effect = [True, False]  # 播放一次后停止

        # 测试数据
        audio_data = b"fake mp3 audio data"

        result = play_audio(audio_data)

        # 验证
        mock_mixer.music.load.assert_called_once()
        mock_mixer.music.play.assert_called_once()
        mock_unlink.assert_called_once()

    @patch('voice_assistant.audio.player.pygame.mixer')
    def test_play_audio_init_mixer(self, mock_mixer):
        """测试初始化 mixer"""
        from voice_assistant.audio.player import play_audio

        # mixer 未初始化
        mock_mixer.get_init.return_value = False
        mock_mixer.music.get_busy.return_value = False

        audio_data = b"test audio"
        play_audio(audio_data)

        mock_mixer.init.assert_called_once()

    @patch('voice_assistant.audio.player.pygame.mixer')
    @patch('voice_assistant.audio.player.os.unlink')
    def test_play_audio_cleanup_on_error(self, mock_unlink, mock_mixer):
        """测试错误时清理临时文件"""
        from voice_assistant.audio.player import play_audio

        mock_mixer.get_init.return_value = True
        mock_mixer.music.load.side_effect = Exception("Load failed")

        audio_data = b"test audio"

        with pytest.raises(Exception):
            play_audio(audio_data)

        # 即使出错也应该尝试清理
        mock_unlink.assert_called_once()

    @patch('voice_assistant.audio.player.pygame.mixer')
    @patch('voice_assistant.audio.player.os.unlink')
    def test_play_audio_cleanup_silent_failure(self, mock_unlink, mock_mixer):
        """测试清理失败时静默处理"""
        from voice_assistant.audio.player import play_audio

        mock_mixer.get_init.return_value = True
        mock_mixer.music.get_busy.return_value = False
        mock_unlink.side_effect = OSError("File not found")

        audio_data = b"test audio"

        # 不应该抛出异常
        play_audio(audio_data)

    @patch('voice_assistant.audio.player.pygame.mixer')
    @patch('voice_assistant.audio.player.time.sleep')
    @patch('voice_assistant.audio.player.os.unlink')
    def test_play_audio_waits_for_completion(self, mock_unlink, mock_sleep, mock_mixer):
        """测试等待播放完成"""
        from voice_assistant.audio.player import play_audio

        mock_mixer.get_init.return_value = True
        # 模拟播放 3 次检查后完成
        mock_mixer.music.get_busy.side_effect = [True, True, False]

        audio_data = b"test audio"
        play_audio(audio_data)

        # 应该等待 2 次（busy 返回 True）
        assert mock_sleep.call_count == 2

    @patch('voice_assistant.audio.player.pygame.mixer')
    @patch('voice_assistant.audio.player.os.unlink')
    def test_play_audio_unloads_after_playback(self, mock_unlink, mock_mixer):
        """测试播放后卸载音频"""
        from voice_assistant.audio.player import play_audio

        mock_mixer.get_init.return_value = True
        mock_mixer.music.get_busy.return_value = False

        audio_data = b"test audio"
        play_audio(audio_data)

        mock_mixer.music.unload.assert_called_once()


class TestPlayAudioIntegration:
    """播放器集成测试"""

    def test_player_module_imports(self):
        """测试模块导入"""
        from voice_assistant.audio.player import play_audio
        assert play_audio is not None

    @patch('voice_assistant.audio.player.pygame.mixer')
    def test_play_audio_with_real_mp3_header(self, mock_mixer):
        """测试播放带有真实 MP3 头的音频"""
        from voice_assistant.audio.player import play_audio

        mock_mixer.get_init.return_value = True
        mock_mixer.music.get_busy.return_value = False

        # 模拟 MP3 文件头
        mp3_header = bytes([0xFF, 0xFB, 0x90, 0x00]) + b"x" * 100
        play_audio(mp3_header)

        mock_mixer.music.load.assert_called_once()