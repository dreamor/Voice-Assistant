"""
云端ASR模块 - 阿里云Paraformer实时语音识别
支持中英文混合识别优化和热词功能
"""
import json
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

import dashscope
import numpy as np

from voice_assistant.config import config
from voice_assistant.security.validation import (
    InputValidationError,
    RateLimitError,
    asr_limiter,
    validate_audio_input,
)

logger = logging.getLogger(__name__)


class HotwordsManager:
    """热词管理器"""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self._vocabulary_id: str | None = None

    def create_vocabulary(self, vocabulary: list, target_model: str = "paraformer-realtime-v2") -> str:
        """创建热词列表

        Args:
            vocabulary: 热词列表，格式如 [{"text": "Python", "weight": 4, "lang": "en"}, ...]
            target_model: 目标 ASR 模型

        Returns:
            热词列表 ID
        """
        try:
            from dashscope.audio.asr import VocabularyService

            service = VocabularyService()
            self._vocabulary_id = service.create_vocabulary(
                target_model=target_model,
                prefix="vasr",
                vocabulary=vocabulary
            )

            if self._vocabulary_id:
                logger.info(f"热词列表创建成功: {self._vocabulary_id}")
                return self._vocabulary_id
            else:
                logger.error("热词列表创建失败: 返回 ID 为空")
                return None

        except ImportError as e:
            logger.error(f"热词模块导入失败，请检查 dashscope 版本: {e}")
            return None
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Throttling" in error_str or "quota" in error_str.lower():
                logger.warning("热词服务配额已用完（免费限额），将使用默认识别。如需热词功能，请升级阿里云付费套餐。")
            else:
                logger.error(f"热词列表创建异常: {type(e).__name__}: {e}")
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

            with open(full_path, encoding='utf-8') as f:
                data = json.load(f)

            return data.get('vocabulary', [])

        except Exception as e:
            logger.warning(f"加载热词配置失败: {e}")
            return []

    @property
    def vocabulary_id(self) -> str | None:
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

        # 初始化热词管理器
        self._hotwords_manager: HotwordsManager | None = None
        self._vocabulary_id: str | None = None

        # 如果启用了热词，初始化热词
        if asr_cfg.hotwords.enabled:
            if asr_cfg.hotwords.vocabulary_id:
                self._vocabulary_id = asr_cfg.hotwords.vocabulary_id
                logger.info(f"使用已注册热词列表: {self._vocabulary_id}")
            else:
                self._init_hotwords(asr_cfg.hotwords.config_file)

    def _configure_dashscope(self):
        """配置 dashscope SDK 全局参数

        注意：dashscope SDK 使用模块级全局变量，无法避免全局变异。
        这是 SDK 的已知限制。在多实例场景中需注意调用顺序。
        """
        dashscope.api_key = self.api_key
        dashscope.base_http_api_url = self.base_url

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

    def recognize_from_file(self, audio_file_path: str, sample_rate: int | None = None) -> str:
        """从音频文件识别 - 使用 DashScope SDK

        Args:
            audio_file_path: WAV文件路径
            sample_rate: 音频采样率，默认从配置读取

        Returns:
            识别的文本，如果识别失败抛出异常

        Raises:
            RuntimeError: 识别失败
        """
        if sample_rate is None:
            sample_rate = config.audio.sample_rate

        # 速率限制检查
        asr_limiter.check()

        try:
            self._configure_dashscope()

            from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

            # 存储识别结果 - 使用 completed_sentences + current_sentence
            # 因为 get_sentence() 返回当前句子的累积文本（非增量），
            # 不能用 += 拼接，否则会产生重复（如 "打开" + "打开计算器" = "打开打开计算器"）
            result_container = {
                "completed_sentences": [],
                "current_sentence": "",
                "finished": False,
                "error": None,
            }

            class ASRCallback(RecognitionCallback):
                def on_open(self):
                    logger.info("  [ASR] Connection opened")

                def on_event(self, result):
                    sentence = result.get_sentence()
                    if sentence and 'text' in sentence:
                        text = sentence['text']
                        if RecognitionResult.is_sentence_end(sentence):
                            # 句子已完成，移入 completed_sentences
                            result_container["completed_sentences"].append(text)
                            result_container["current_sentence"] = ""
                            logger.info(f"  [ASR] Sentence end: {text}")
                        else:
                            # 句子仍在更新中，只覆盖 current_sentence
                            result_container["current_sentence"] = text
                            logger.info(f"  [ASR] Partial: {text}")

                def on_complete(self):
                    logger.info("  [ASR] Complete")
                    result_container["finished"] = True

                def on_error(self, result):
                    logger.error(f"  [ASR] Error: {result.get_sentence()}")
                    result_container["error"] = str(result)
                    result_container["finished"] = True

                def on_close(self):
                    logger.info("  [ASR] Connection closed")

            # 读取音频文件
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()

            # 如果是 WAV 格式，使用 wave 模块正确提取 PCM 数据
            if audio_data[:4] == b'RIFF':
                import wave as wave_mod
                with wave_mod.open(audio_file_path, 'rb') as wf:
                    audio_data = wf.readframes(wf.getnframes())

            # 创建 Recognition 对象
            recognition = Recognition(
                model=self.model,
                format='wav',
                sample_rate=sample_rate,
                language_hints=self.language_hints or ["zh", "en"],
                disfluency_removal_enabled=self.disfluency_removal_enabled,
                max_sentence_silence=self.max_sentence_silence,
                vocabulary_id=self._vocabulary_id,
                callback=ASRCallback()
            )

            # 开始识别
            recognition.start()

            # 发送音频数据（分块发送，每块约 16KB）
            chunk_size = 16000
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                recognition.send_audio_frame(chunk)

            # 停止识别
            recognition.stop()

            # 等待结果（最多30秒）
            import time
            start = time.time()
            while not result_container["finished"] and time.time() - start < 30:
                time.sleep(0.1)

            if result_container["error"]:
                raise RuntimeError(f"云端ASR错误: {result_container['error']}")

            all_sentences = result_container["completed_sentences"] + [result_container["current_sentence"]]
            final_text = "".join(s for s in all_sentences if s)
            if final_text:
                return final_text

            return ""

        except Exception as e:
            logger.error(f"ASR 识别失败: {e}")
            raise RuntimeError(f"云端ASR错误: {e}") from e

    def recognize_from_bytes(self, audio_bytes: bytes, sample_rate: int | None = None) -> str:
        """从音频字节数据识别

        Args:
            audio_bytes: 音频数据（可以是WAV格式或原始PCM数据）
            sample_rate: 采样率，默认从配置读取

        Returns:
            识别的文本

        Raises:
            RateLimitError: 超过速率限制
            InputValidationError: 输入验证失败
            RuntimeError: 识别失败
        """
        import soundfile as sf

        if sample_rate is None:
            sample_rate = config.audio.sample_rate

        # 输入验证
        validate_audio_input(audio_bytes)

        # 速率限制检查
        asr_limiter.check()

        try:
            self._configure_dashscope()

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
                    logger.debug("[CloudASR] 临时文件清理失败（可忽略）")

        except (RateLimitError, InputValidationError):
            raise
        except Exception as e:
            raise RuntimeError(f"云端ASR错误: {e}") from e

    def recognize_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """ASRProvider 协议接口：从音频字节数据识别文本

        委托给 recognize_from_bytes 实现。

        Args:
            audio_bytes: 音频数据（WAV 格式或原始 PCM）
            sample_rate: 采样率

        Returns:
            识别的文本，识别失败返回空字符串
        """
        try:
            return self.recognize_from_bytes(audio_bytes, sample_rate=sample_rate)
        except Exception as e:
            logger.error(f"ASR recognize_bytes 失败: {e}")
            return ""

    def close(self) -> None:
        """释放资源（云端 ASR 无需特殊清理）"""
        pass


class RealtimeASRSession:
    """流式 ASR 会话：边录边识别，语义完整时触发回调。

    用法：
        session = RealtimeASRSession(on_sentence_end=..., on_error=...)
        session.start()
        session.send_chunk(pcm_int16_bytes)  # 多次调用
        session.stop()                        # 结束并等待最终结果
    """

    def __init__(
        self,
        on_sentence_end: "Callable[[str], None]",
        on_error: "Callable[[str], None] | None" = None,
        sample_rate: int | None = None,
    ):
        self._on_sentence_end = on_sentence_end
        self._on_error = on_error
        self._sample_rate = sample_rate or config.audio.sample_rate
        self._recognition = None
        self._completed: list[str] = []
        self._current = ""
        self._started = False

    def start(self) -> None:
        from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

        asr_cfg = config.asr
        dashscope.api_key = asr_cfg.api_key
        dashscope.base_http_api_url = asr_cfg.base_url

        completed = self._completed
        current_box = [""]
        on_sentence_end = self._on_sentence_end
        on_error = self._on_error

        class _CB(RecognitionCallback):
            def on_event(self, result):
                sentence = result.get_sentence()
                if not sentence or 'text' not in sentence:
                    return
                text = sentence['text']
                if RecognitionResult.is_sentence_end(sentence):
                    completed.append(text)
                    current_box[0] = ""
                    logger.info(f"[RealtimeASR] sentence_end: {text}")
                    full = "".join(completed)
                    on_sentence_end(full)
                else:
                    current_box[0] = text

            def on_complete(self):
                logger.info("[RealtimeASR] complete")

            def on_error(self, result):
                msg = str(result)
                logger.error(f"[RealtimeASR] error: {msg}")
                if on_error:
                    on_error(msg)

            def on_open(self):
                logger.info("[RealtimeASR] opened")

            def on_close(self):
                logger.info("[RealtimeASR] closed")

        vocabulary_id = None
        if asr_cfg.hotwords.enabled and asr_cfg.hotwords.vocabulary_id:
            vocabulary_id = asr_cfg.hotwords.vocabulary_id

        self._recognition = Recognition(
            model=asr_cfg.model,
            format='pcm',
            sample_rate=self._sample_rate,
            language_hints=asr_cfg.language_hints or ["zh", "en"],
            disfluency_removal_enabled=asr_cfg.disfluency_removal_enabled,
            max_sentence_silence=asr_cfg.max_sentence_silence,
            vocabulary_id=vocabulary_id,
            callback=_CB(),
        )
        self._recognition.start()
        self._started = True
        logger.info("[RealtimeASR] session started")

    def send_chunk(self, pcm_bytes: bytes) -> None:
        if self._started and self._recognition:
            self._recognition.send_audio_frame(pcm_bytes)

    def stop(self) -> None:
        if self._started and self._recognition:
            self._recognition.stop()
            self._started = False
            logger.info("[RealtimeASR] session stopped")
