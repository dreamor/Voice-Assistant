"""
TTS (Text-to-Speech) 模块
使用 Edge-TTS 进行语音合成
"""
import logging
import re
import asyncio
import edge_tts
from config import config

logger = logging.getLogger(__name__)


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
        asyncio.run(_synthesize_async(processed_text, output_file))
        return True
    except Exception as e:
        logger.error(f"TTS错误: {e}")
        return False


if __name__ == "__main__":
    print(f"Edge TTS Voice: {config.audio.edge_tts_voice}")