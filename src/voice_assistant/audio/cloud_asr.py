"""
云端ASR模块 - 阿里云Paraformer实时语音识别
支持中英文混合识别优化和热词功能
"""
import json
import logging
import os
import tempfile
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import dashscope
import numpy as np
from dashscope.audio.asr import Recognition, Transcription
from voice_assistant.config import config
from voice_assistant.security.validation import validate_audio_input, asr_limiter, RateLimitError

logger = logging.getLogger(__name__)


class HotwordsManager:
    """热词管理器"""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        dashscope.api_key = api_key
        dashscope.base_http_api_url = base_url
        self._vocabulary_id: Optional[str] = None

    def create_vocabulary(self, vocabulary: list, target_model: str = "paraformer-realtime-v2") -> str:
        """创建热词列表

        Args:
            vocabulary: 热词列表，格式如 [{"text": "Python", "weight": 4, "lang": "en"}, ...]
            target_model: 目标 ASR 模型

        Returns:
            热词列表 ID
        """
        try:
            from dashscope.audio.asr import AsrPhraseManager

            manager = AsrPhraseManager()
            result = manager.create_vocabulary(
                target_model=target_model,
                prefix="voice_assistant",
                vocabulary=vocabulary
            )

            if result.status_code == HTTPStatus.OK:
                self._vocabulary_id = result.output.get('vocabulary_id')
                logger.info(f"热词列表创建成功: {self._vocabulary_id}")
                return self._vocabulary_id
            else:
                logger.error(f"热词列表创建失败: {result.code} - {result.message}")
                return None

        except Exception as e:
            logger.error(f"热词列表创建异常: {e}")
            return None

    def load_hotwords_from_file(self, config_file: str) -> list:
        """从配置文件加载热词

        Args:
            config_file: 热词配置文件路径

        Returns:
            热词列表
        """
        try:
            # 查找项目根目录
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            full_path = project_root / config_file

            with open(full_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return data.get('vocabulary', [])

        except Exception as e:
            logger.warning(f"加载热词配置失败: {e}")
            return []

    @property
    def vocabulary_id(self) -> Optional[str]:
        return self._vocabulary_id


class CloudASR:
    """云端语音识别类，支持中英文混合识别优化"""

    def __init__(self, api_key=None, model=None):
        """初始化云端ASR"""
        asr_cfg = config.asr
        self.api_key = api_key or asr_cfg.api_key
        self.model = model or asr_cfg.model
        self.base_url = asr_cfg.base_url
        self.language_hints = asr_cfg.language_hints
        self.disfluency_removal_enabled = asr_cfg.disfluency_removal_enabled
        self.max_sentence_silence = asr_cfg.max_sentence_silence

        dashscope.api_key = self.api_key
        dashscope.base_http_api_url = self.base_url

        # 初始化热词管理器
        self._hotwords_manager: Optional[HotwordsManager] = None
        self._vocabulary_id: Optional[str] = None

        # 如果启用了热词，初始化热词
        if asr_cfg.hotwords.enabled:
            self._init_hotwords(asr_cfg.hotwords.config_file)

    def _init_hotwords(self, config_file: str):
        """初始化热词功能"""
        self._hotwords_manager = HotwordsManager(self.api_key, self.base_url)

        # 加载热词配置
        vocabulary = self._hotwords_manager.load_hotwords_from_file(config_file)

        if vocabulary:
            # 创建热词列表
            self._vocabulary_id = self._hotwords_manager.create_vocabulary(vocabulary)
            if self._vocabulary_id:
                logger.info(f"热词功能已启用，共 {len(vocabulary)} 个热词")
            else:
                logger.warning("热词列表创建失败，将使用默认识别")
        else:
            logger.warning("热词配置为空，跳过热词初始化")

    def recognize_from_file(self, audio_file_path: str, sample_rate: Optional[int] = None) -> str:
        """从音频文件识别

        Args:
            audio_file_path: WAV文件路径
            sample_rate: 音频采样率，默认从配置读取

        Returns:
            识别的文本，如果识别失败返回错误信息

        Raises:
            RateLimitError: 超过速率限制
        """
        if sample_rate is None:
            sample_rate = config.audio.sample_rate

        # 速率限制检查
        asr_limiter.check()

        try:
            # 构建识别参数
            recognition_params = {
                'model': self.model,
                'format': 'wav',
                'sample_rate': sample_rate,
                'language_hints': self.language_hints,
                'disfluency_removal_enabled': self.disfluency_removal_enabled,
                'max_sentence_silence': self.max_sentence_silence,
            }

            # 如果有热词 ID，添加到参数中
            if self._vocabulary_id:
                recognition_params['vocabulary_id'] = self._vocabulary_id

            recognition = Recognition(**recognition_params)
            result = recognition.call(audio_file_path)

            if result.status_code == HTTPStatus.OK and result.output:
                sentences = result.output.get('sentence', [])
                if sentences:
                    text_parts = []
                    for sent in sentences:
                        if isinstance(sent, dict) and 'text' in sent:
                            text_parts.append(sent['text'])
                    if text_parts:
                        return ''.join(text_parts)

            return "未识别到内容"

        except Exception as e:
            return f"云端ASR错误: {e}"

    def recognize_from_bytes(self, audio_bytes: bytes, sample_rate: Optional[int] = None) -> str:
        """从音频字节数据识别

        Args:
            audio_bytes: 音频数据（可以是WAV格式或原始PCM数据）
            sample_rate: 采样率，默认从配置读取

        Returns:
            识别的文本，如果识别失败返回错误信息

        Raises:
            RateLimitError: 超过速率限制
            InputValidationError: 输入验证失败
        """
        import soundfile as sf

        if sample_rate is None:
            sample_rate = config.audio.sample_rate

        # 输入验证
        validate_audio_input(audio_bytes)

        # 速率限制检查
        asr_limiter.check()

        try:
            if audio_bytes[:4] == b'RIFF':
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, mode='wb') as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
            else:
                try:
                    audio_data = np.frombuffer(audio_bytes, dtype=np.float32)
                    if audio_data.max() <= 1.0:
                        audio_data = (audio_data * 32767).astype(np.int16)
                except (ValueError, TypeError):
                    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    sf.write(tmp.name, audio_data, sample_rate, format='WAV')
                    tmp_path = tmp.name

            try:
                return self.recognize_from_file(tmp_path, sample_rate)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except Exception as e:
            return f"云端ASR错误: {e}"