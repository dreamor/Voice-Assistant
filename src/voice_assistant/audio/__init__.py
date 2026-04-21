"""音频处理模块"""

from voice_assistant.audio.vad import record_audio, calculate_rms
from voice_assistant.audio.tts import synthesize, preprocess_text
from voice_assistant.audio.player import play_audio
from voice_assistant.audio.cloud_asr import CloudASR
from voice_assistant.audio.asr_provider import ASRProvider, create_asr_provider

__all__ = [
    'record_audio',
    'calculate_rms',
    'synthesize',
    'preprocess_text',
    'play_audio',
    'CloudASR',
    'ASRProvider',
    'create_asr_provider',
]
