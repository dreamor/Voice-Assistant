"""
TTS (Text-to-Speech) 模块
支持多 TTS 引擎的可替换架构，基于 TTSProvider 协议
"""
import asyncio
import logging
import re
from typing import Protocol, runtime_checkable, Optional, Dict, Type

logger = logging.getLogger(__name__)

# 模块级事件循环（避免每次调用 asyncio.run() 创建新循环）
_tts_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_tts_loop() -> asyncio.AbstractEventLoop:
    """获取或创建 TTS 专用事件循环"""
    global _tts_loop
    if _tts_loop is None or _tts_loop.is_closed():
        _tts_loop = asyncio.new_event_loop()
    return _tts_loop


def preprocess_text(text: str) -> str:
    """文本预处理，使TTS发音更自然"""
    text = re.sub(r'([。！？])', r'\1  ', text)
    text = re.sub(r'([，；：])', r'\1 ', text)
    text = re.sub(r' +', ' ', text).strip()
    return text


# ---------------------------------------------------------------------------
# TTS Provider 协议
# ---------------------------------------------------------------------------

@runtime_checkable
class TTSProvider(Protocol):
    """TTS 提供者协议

    所有 TTS 后端都必须实现此协议，
    使上层代码不再需要 if/else 切换。
    """

    def synthesize(self, text: str, output_file: str) -> bool:
        """将文本合成为语音文件

        Args:
            text: 要合成的文本
            output_file: 输出音频文件路径

        Returns:
            是否成功
        """
        ...

    def synthesize_to_bytes(self, text: str) -> Optional[bytes]:
        """将文本合成为音频字节数据

        Args:
            text: 要合成的文本

        Returns:
            音频数据（格式取决于实现），失败返回 None
        """
        ...

    def synthesize_stream(self, text: str):
        """流式合成：逐句/逐块 yield 音频数据

        Args:
            text: 要合成的文本

        Yields:
            bytes: 音频数据块（MP3 格式）
        """
        ...

    def close(self) -> None:
        """释放资源"""
        ...


# ---------------------------------------------------------------------------
# EdgeTTS Provider 实现
# ---------------------------------------------------------------------------

class EdgeTTSProvider:
    """Edge-TTS 语音合成提供者"""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "", pitch: str = ""):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """获取或创建事件循环"""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def _build_communicate_kwargs(self) -> dict:
        """构建 edge_tts.Communicate 的关键字参数"""
        kwargs: dict = {"voice": self.voice}
        if self.rate:
            kwargs["rate"] = self.rate
        if self.pitch:
            kwargs["pitch"] = self.pitch
        return kwargs

    async def _synthesize_async(self, text: str, output_file: str) -> None:
        """异步合成语音到文件"""
        import edge_tts

        communicate = edge_tts.Communicate(text, **self._build_communicate_kwargs())
        await communicate.save(output_file)

    async def _synthesize_bytes_async(self, text: str) -> Optional[bytes]:
        """异步合成语音到字节数据"""
        import edge_tts
        import io

        communicate = edge_tts.Communicate(text, **self._build_communicate_kwargs())
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        return buffer.getvalue() if buffer.getvalue() else None

    def synthesize(self, text: str, output_file: str) -> bool:
        """同步接口：将文本合成为语音文件"""
        try:
            processed_text = preprocess_text(text)
            loop = self._get_loop()
            loop.run_until_complete(self._synthesize_async(processed_text, output_file))
            return True
        except RuntimeError as e:
            if "Event loop is closed" in str(e) or "cannot schedule new futures" in str(e):
                self._loop = asyncio.new_event_loop()
                self._loop.run_until_complete(self._synthesize_async(processed_text, output_file))
                return True
            logger.error(f"TTS错误: {e}")
            return False
        except Exception as e:
            logger.error(f"TTS错误: {e}")
            return False

    def synthesize_to_bytes(self, text: str) -> Optional[bytes]:
        """同步接口：将文本合成为音频字节数据"""
        try:
            processed_text = preprocess_text(text)
            loop = self._get_loop()
            return loop.run_until_complete(self._synthesize_bytes_async(processed_text))
        except RuntimeError as e:
            if "Event loop is closed" in str(e) or "cannot schedule new futures" in str(e):
                self._loop = asyncio.new_event_loop()
                return self._loop.run_until_complete(self._synthesize_bytes_async(processed_text))
            logger.error(f"TTS错误: {e}")
            return None
        except Exception as e:
            logger.error(f"TTS错误: {e}")
            return None

    def close(self) -> None:
        """释放资源"""
        if self._loop and not self._loop.is_closed():
            self._loop.close()
            self._loop = None

    def _split_sentences(self, text: str) -> list[str]:
        """将文本按句子分割，用于流式合成

        Args:
            text: 输入文本

        Returns:
            句子列表
        """
        # 按中文标点分割，保留标点
        import re
        sentences = re.split(r'([。！？；\n]+)', text)
        # 合并标点和内容
        result = []
        for i in range(0, len(sentences) - 1, 2):
            result.append(sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else ''))
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1])
        # 过滤空句子
        return [s.strip() for s in result if s.strip()]

    async def _synthesize_sentence_async(self, sentence: str) -> Optional[bytes]:
        """异步合成单个句子"""
        import edge_tts
        import io

        try:
            communicate = edge_tts.Communicate(sentence, **self._build_communicate_kwargs())
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])
            return buffer.getvalue() if buffer.getvalue() else None
        except Exception as e:
            logger.error(f"句子合成失败: {e}")
            return None

    def synthesize_stream(self, text: str):
        """流式合成：逐句 yield 音频数据

        Args:
            text: 要合成的文本

        Yields:
            bytes: 音频数据块（MP3 格式）
        """
        if not text or not text.strip():
            return

        processed_text = preprocess_text(text)
        sentences = self._split_sentences(processed_text)

        if not sentences:
            # 没有可分割的句子，整体合成
            result = self.synthesize_to_bytes(processed_text)
            if result:
                yield result
            return

        for sentence in sentences:
            if not sentence.strip():
                continue
            try:
                loop = self._get_loop()
                audio_data = loop.run_until_complete(
                    self._synthesize_sentence_async(sentence)
                )
                if audio_data:
                    yield audio_data
            except RuntimeError as e:
                if "Event loop is closed" in str(e) or "cannot schedule new futures" in str(e):
                    self._loop = asyncio.new_event_loop()
                    audio_data = self._loop.run_until_complete(
                        self._synthesize_sentence_async(sentence)
                    )
                    if audio_data:
                        yield audio_data
                else:
                    logger.error(f"流式TTS错误: {e}")
            except Exception as e:
                logger.error(f"流式TTS错误: {e}")


# ---------------------------------------------------------------------------
# TTS Provider 注册表
# ---------------------------------------------------------------------------

_TTS_REGISTRY: Dict[str, Type] = {}


def register_tts_provider(name: str, cls: type) -> None:
    """注册 TTS 提供者

    Args:
        name: 提供者名称（如 "edge-tts", "azure", "local"）
        cls: 实现 TTSProvider 协议的类

    Raises:
        TypeError: cls 不是类
    """
    if not isinstance(cls, type):
        raise TypeError(f"TTS 提供者必须是类，收到 {type(cls)}")
    if name in _TTS_REGISTRY:
        logger.warning(f"TTS 提供者 '{name}' 已存在，将被覆盖")
    _TTS_REGISTRY[name] = cls
    logger.debug(f"注册 TTS 提供者: {name}")


# 默认注册 EdgeTTS
register_tts_provider("edge-tts", EdgeTTSProvider)


def create_tts_provider(config) -> TTSProvider:
    """根据配置创建 TTS 提供者

    Args:
        config: AppConfig 配置对象

    Returns:
        TTSProvider 实例

    Raises:
        ValueError: 未知的 TTS 提供者名称
    """
    # 兼容旧配置：从 tts 或 audio.edge_tts_voice 读取
    tts_cfg = getattr(config, 'tts', None)
    if tts_cfg is not None:
        provider_name = tts_cfg.provider
        voice = tts_cfg.voice
        rate = getattr(tts_cfg, 'rate', '') or ''
        pitch = getattr(tts_cfg, 'pitch', '') or ''
    else:
        # 向后兼容：从 AudioConfig 读取
        provider_name = "edge-tts"
        voice = config.audio.edge_tts_voice
        rate = ""
        pitch = ""

    if provider_name not in _TTS_REGISTRY:
        available = ", ".join(_TTS_REGISTRY.keys()) or "(无)"
        raise ValueError(
            f"未知的 TTS 提供者: '{provider_name}'，可用提供者: {available}"
        )

    cls = _TTS_REGISTRY[provider_name]

    # EdgeTTS 特殊初始化
    if provider_name == "edge-tts":
        provider = cls(voice=voice, rate=rate, pitch=pitch)
    else:
        provider = cls()

    logger.info(f"TTS 提供者: {provider_name} (voice={voice})")
    return provider


# ---------------------------------------------------------------------------
# 向后兼容的模块级函数
# ---------------------------------------------------------------------------

_default_provider: Optional[EdgeTTSProvider] = None


def _get_default_provider() -> EdgeTTSProvider:
    """获取默认 EdgeTTS 提供者（向后兼容）"""
    global _default_provider
    if _default_provider is None:
        from voice_assistant.config import config as app_config
        tts_cfg = getattr(app_config, 'tts', None)
        if tts_cfg is not None:
            voice = tts_cfg.voice
        else:
            voice = app_config.audio.edge_tts_voice
        _default_provider = EdgeTTSProvider(voice=voice)
    return _default_provider


def synthesize(text: str, output_file: str) -> bool:
    """同步接口：将文本转换为语音（向后兼容）

    Args:
        text: 要合成的文本
        output_file: 输出音频文件路径（MP3格式）

    Returns:
        是否成功
    """
    provider = _get_default_provider()
    return provider.synthesize(text, output_file)


def cleanup_tts():
    """清理 TTS 事件循环资源"""
    global _tts_loop, _default_provider
    if _default_provider is not None:
        _default_provider.close()
        _default_provider = None
    if _tts_loop and not _tts_loop.is_closed():
        _tts_loop.close()
        _tts_loop = None