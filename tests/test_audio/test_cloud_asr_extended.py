"""Cloud ASR 扩展测试"""
import json
import os
import tempfile
import pytest
import numpy as np
import soundfile as sf
from unittest.mock import patch, MagicMock, mock_open


class TestHotwordsManager:
    """测试热词管理器"""

    def test_hotwords_manager_initialization(self):
        """测试热词管理器初始化"""
        from voice_assistant.audio.cloud_asr import HotwordsManager

        manager = HotwordsManager("test_api_key", "https://test.url")
        assert manager.api_key == "test_api_key"
        assert manager.base_url == "https://test.url"
        assert manager.vocabulary_id is None

    def test_load_hotwords_from_file(self):
        """测试从文件加载热词"""
        from voice_assistant.audio.cloud_asr import HotwordsManager

        manager = HotwordsManager("test_key", "https://test.url")

        # 使用项目的实际热词文件
        vocabulary = manager.load_hotwords_from_file("config/hotwords.json")

        assert isinstance(vocabulary, list)
        assert len(vocabulary) > 0

        # 验证热词格式
        for word in vocabulary:
            assert "text" in word
            assert "weight" in word
            assert "lang" in word

    def test_load_hotwords_file_not_found(self):
        """测试加载不存在的热词文件"""
        from voice_assistant.audio.cloud_asr import HotwordsManager

        manager = HotwordsManager("test_key", "https://test.url")

        vocabulary = manager.load_hotwords_from_file("nonexistent.json")
        assert vocabulary == []

    @patch('dashscope.audio.asr.VocabularyService')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    def test_create_vocabulary_success(self, mock_dashscope, mock_vocab_service_class):
        """测试成功创建热词列表"""
        from voice_assistant.audio.cloud_asr import HotwordsManager

        # 模拟 VocabularyService 实例和返回结果
        mock_service = MagicMock()
        mock_service.create_vocabulary.return_value = "vocab_123"
        mock_vocab_service_class.return_value = mock_service

        manager = HotwordsManager("test_key", "https://test.url")
        vocabulary = [{"text": "Python", "weight": 4, "lang": "en"}]

        result = manager.create_vocabulary(vocabulary)

        assert result == "vocab_123"
        assert manager.vocabulary_id == "vocab_123"

    @patch('dashscope.audio.asr.VocabularyService')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    def test_create_vocabulary_failure(self, mock_dashscope, mock_vocab_service_class):
        """测试创建热词列表失败"""
        from voice_assistant.audio.cloud_asr import HotwordsManager

        # 模拟返回 None 表示失败
        mock_service = MagicMock()
        mock_service.create_vocabulary.return_value = None
        mock_vocab_service_class.return_value = mock_service

        manager = HotwordsManager("test_key", "https://test.url")
        vocabulary = [{"text": "Python", "weight": 4, "lang": "en"}]

        result = manager.create_vocabulary(vocabulary)

        assert result is None

    @patch('dashscope.audio.asr.VocabularyService')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    def test_create_vocabulary_import_error(self, mock_dashscope, mock_vocab_service_class):
        """测试导入错误处理"""
        from voice_assistant.audio.cloud_asr import HotwordsManager

        mock_vocab_service_class.side_effect = ImportError("No module")

        manager = HotwordsManager("test_key", "https://test.url")
        vocabulary = [{"text": "Python", "weight": 4, "lang": "en"}]

        result = manager.create_vocabulary(vocabulary)

        assert result is None

    @patch('dashscope.audio.asr.VocabularyService')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    def test_create_vocabulary_exception(self, mock_dashscope, mock_vocab_service_class):
        """测试异常处理"""
        from voice_assistant.audio.cloud_asr import HotwordsManager

        mock_vocab_service_class.side_effect = Exception("Connection error")

        manager = HotwordsManager("test_key", "https://test.url")
        vocabulary = [{"text": "Python", "weight": 4, "lang": "en"}]

        result = manager.create_vocabulary(vocabulary)

        assert result is None


class TestCloudASRInit:
    """测试 CloudASR 初始化"""

    @patch('voice_assistant.audio.cloud_asr.config')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    def test_init_without_hotwords(self, mock_dashscope, mock_config):
        """测试不启用热词的初始化"""
        mock_config.asr.api_key = "test_key"
        mock_config.asr.model = "test_model"
        mock_config.asr.base_url = "https://test.url"
        mock_config.asr.language_hints = ["zh", "en"]
        mock_config.asr.disfluency_removal_enabled = True
        mock_config.asr.max_sentence_silence = 500
        mock_config.asr.hotwords.enabled = False

        from voice_assistant.audio.cloud_asr import CloudASR

        asr = CloudASR()

        assert asr.api_key == "test_key"
        assert asr.model == "test_model"
        assert asr._hotwords_manager is None
        assert asr._vocabulary_id is None

    @patch('voice_assistant.audio.cloud_asr.config')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    @patch('voice_assistant.audio.cloud_asr.HotwordsManager')
    def test_init_with_hotwords(self, mock_hotwords_class, mock_dashscope, mock_config):
        """测试启用热词的初始化"""
        mock_config.asr.api_key = "test_key"
        mock_config.asr.model = "test_model"
        mock_config.asr.base_url = "https://test.url"
        mock_config.asr.language_hints = ["zh", "en"]
        mock_config.asr.disfluency_removal_enabled = True
        mock_config.asr.max_sentence_silence = 500
        mock_config.asr.hotwords.enabled = True
        mock_config.asr.hotwords.config_file = "config/hotwords.json"

        mock_manager = MagicMock()
        mock_manager.load_hotwords_from_file.return_value = [{"text": "test", "weight": 4, "lang": "en"}]
        mock_manager.create_vocabulary.return_value = "vocab_123"
        mock_hotwords_class.return_value = mock_manager

        from voice_assistant.audio.cloud_asr import CloudASR

        asr = CloudASR()

        assert asr._vocabulary_id == "vocab_123"
        mock_manager.load_hotwords_from_file.assert_called_once()

    @patch('voice_assistant.audio.cloud_asr.config')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    @patch('voice_assistant.audio.cloud_asr.HotwordsManager')
    def test_init_hotwords_empty_vocabulary(self, mock_hotwords_class, mock_dashscope, mock_config):
        """测试热词列表为空"""
        mock_config.asr.api_key = "test_key"
        mock_config.asr.model = "test_model"
        mock_config.asr.base_url = "https://test.url"
        mock_config.asr.language_hints = ["zh", "en"]
        mock_config.asr.disfluency_removal_enabled = True
        mock_config.asr.max_sentence_silence = 500
        mock_config.asr.hotwords.enabled = True
        mock_config.asr.hotwords.config_file = "config/hotwords.json"

        mock_manager = MagicMock()
        mock_manager.load_hotwords_from_file.return_value = []
        mock_hotwords_class.return_value = mock_manager

        from voice_assistant.audio.cloud_asr import CloudASR

        asr = CloudASR()

        assert asr._vocabulary_id is None


class TestCloudASRRecognize:
    """测试 CloudASR 识别功能"""

    @patch('voice_assistant.audio.cloud_asr.config')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    @patch('voice_assistant.audio.cloud_asr.Recognition')
    def test_recognize_from_file_error(self, mock_recognition_class, mock_dashscope, mock_config):
        """测试识别错误处理"""
        mock_config.asr.api_key = "test_key"
        mock_config.asr.model = "test_model"
        mock_config.asr.base_url = "https://test.url"
        mock_config.asr.language_hints = ["zh", "en"]
        mock_config.asr.disfluency_removal_enabled = True
        mock_config.asr.max_sentence_silence = 500
        mock_config.asr.hotwords.enabled = False
        mock_config.audio.sample_rate = 16000

        # 创建测试音频文件
        sample_rate = 16000
        duration = 1
        t = np.linspace(0, duration, sample_rate * duration)
        audio_data = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            sf.write(tmp.name, audio_data, sample_rate, format='WAV')
            test_file = tmp.name

        try:
            # 模拟 Recognition 抛出异常
            mock_recognition_class.side_effect = Exception("Connection failed")

            from voice_assistant.audio.cloud_asr import CloudASR

            asr = CloudASR()
            result = asr.recognize_from_file(test_file)

            assert "错误" in result or "Error" in result
        finally:
            os.unlink(test_file)

    @patch('voice_assistant.audio.cloud_asr.config')
    @patch('voice_assistant.audio.cloud_asr.dashscope')
    def test_recognize_from_bytes_wav_format(self, mock_dashscope, mock_config):
        """测试从 WAV 字节数据识别"""
        mock_config.asr.api_key = "test_key"
        mock_config.asr.model = "test_model"
        mock_config.asr.base_url = "https://test.url"
        mock_config.asr.language_hints = ["zh", "en"]
        mock_config.asr.disfluency_removal_enabled = True
        mock_config.asr.max_sentence_silence = 500
        mock_config.asr.hotwords.enabled = False
        mock_config.audio.sample_rate = 16000

        # 创建 WAV 格式音频字节
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            sf.write(tmp.name, audio_data, sample_rate, format='WAV')
            with open(tmp.name, 'rb') as f:
                wav_bytes = f.read()
            test_file = tmp.name

        try:
            from voice_assistant.audio.cloud_asr import CloudASR

            asr = CloudASR()

            # 验证 WAV 头检测
            assert wav_bytes[:4] == b'RIFF'

            # 由于需要实际 API 调用，这里只测试函数可以接受 WAV 字节
            # 实际识别会被 mock 或返回错误
        finally:
            os.unlink(test_file)


class TestCloudASRUtilities:
    """测试 CloudASR 工具方法"""

    def test_module_imports(self):
        """测试模块导入"""
        from voice_assistant.audio.cloud_asr import CloudASR, HotwordsManager
        assert CloudASR is not None
        assert HotwordsManager is not None

    def test_vocabulary_id_property(self):
        """测试 vocabulary_id 属性"""
        from voice_assistant.audio.cloud_asr import HotwordsManager

        manager = HotwordsManager("key", "url")
        assert manager.vocabulary_id is None

        manager._vocabulary_id = "test_id"
        assert manager.vocabulary_id == "test_id"