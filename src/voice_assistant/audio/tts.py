"""
TTS (Text-to-Speech) 模块
使用 Edge-TTS 进行语音合成
"""
import asyncio
import logging
import re

import edge_tts

from voice_assistant.config import config

logger = logging.getLogger(__name__)

# 模块级事件循环（避免每次调用 asyncio.run() 创建新循环）
_tts_loop: asyncio.AbstractEventLoop | None = None


def _get_tts_loop() -> asyncio.AbstractEventLoop:
    """获取或创建 TTS 专用事件循环
    
    使用模块级事件循环，避免 asyncio.run() 在已有事件循环时崩溃，
    同时避免每次调用都创建新循环的开销。
    """
    global _tts_loop
    if _tts_loop is None or _tts_loop.is_closed():
        _tts_loop = asyncio.new_event_loop()
    return _tts_loop


def preprocess_text(text):
    """文本预处理，使TTS发音更自然"""
    text = re.sub(r'([。！？])', r'\1  ', text)
    text = re.sub(r'([，；：])', r'\1 ', text)
    text = re.sub(r' +', ' ', text).strip()
    return text


async def _synthesize_async(text, output_file):
    """异步合成语音"""
    voice = config.audio.edge_tts_voice
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)


def synthesize(text, output_file):
    """同步接口：将文本转换为语音

    Args:
        text: 要合成的文本
        output_file: 输出音频文件路径（MP3格式）

    Returns:
        bool: 是否成功
    """
    try:
        processed_text = preprocess_text(text)
        loop = _get_tts_loop()
        loop.run_until_complete(_synthesize_async(processed_text, output_file))
        return True
    except RuntimeError as e:
        # 如果当前线程已有运行中的事件循环（如 Web UI 场景），使用新线程
        if "Event loop is closed" in str(e) or "cannot schedule new futures" in str(e):
            global _tts_loop
            _tts_loop = asyncio.new_event_loop()
            _tts_loop.run_until_complete(_synthesize_async(processed_text, output_file))
            return True
        logger.error(f"TTS错误: {e}")
        return False
    except Exception as e:
        logger.error(f"TTS错误: {e}")
        return False


def cleanup_tts():
    """清理 TTS 事件循环资源"""
    global _tts_loop
    if _tts_loop and not _tts_loop.is_closed():
        _tts_loop.close()
        _tts_loop = None
