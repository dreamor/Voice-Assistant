"""
TTS (Text-to-Speech) 模块
使用 Edge-TTS 进行语音合成
"""
import os
import re
import asyncio
import edge_tts
from dotenv import load_dotenv

load_dotenv()

EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE")


def preprocess_text(text):
    """文本预处理，使TTS发音更自然"""
    text = re.sub(r'([。！？])', r'\1  ', text)
    text = re.sub(r'([，；：])', r'\1 ', text)
    text = re.sub(r' +', ' ', text).strip()
    return text


def synthesize(text):
    """语音合成"""
    processed = preprocess_text(text)

    async def generate():
        communicate = edge_tts.Communicate(processed, EDGE_TTS_VOICE)
        audio = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return audio

    return asyncio.run(generate())
