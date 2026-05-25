"""音频格式转换工具"""
import io
import logging
import wave

import numpy as np

logger = logging.getLogger(__name__)


def convert_audio_to_wav(audio_bytes: bytes, audio_format: str = "audio/wav") -> bytes:
    """将音频数据转换为 WAV 格式（16kHz 单声道）

    支持 PCM 原始数据、WebM/OGG 等格式。
    PCM 数据直接包装为 WAV，其他格式使用 pydub 转换。
    转换失败时返回原始数据并记录警告。

    Args:
        audio_bytes: 原始音频字节数据
        audio_format: MIME 类型（如 audio/pcm, audio/webm, audio/ogg, audio/wav）

    Returns:
        WAV 格式音频字节数据（16kHz 单声道），或原始数据（转换失败时）
    """
    # PCM 格式：直接包装为 WAV
    if "pcm" in audio_format.lower():
        try:
            sample_rate = 16000
            if "rate=" in audio_format:
                try:
                    rate_str = audio_format.split("rate=")[1].split(";")[0].split(",")[0]
                    sample_rate = int(rate_str)
                except (ValueError, IndexError):
                    sample_rate = 16000

            out = io.BytesIO()
            with wave.open(out, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)

            wav_data = out.getvalue()
            logger.info(f"[WebUI] PCM -> WAV 转换完成: {len(audio_bytes)} -> {len(wav_data)} bytes, 采样率: {sample_rate}")
            return wav_data
        except Exception as e:
            logger.error(f"[WebUI] PCM 转 WAV 失败: {e}")
            return audio_bytes

    # WAV 格式：尝试重采样到 16kHz 单声道
    if "wav" in audio_format.lower():
        try:
            import soundfile as sf
            buffer = io.BytesIO(audio_bytes)
            data, sr = sf.read(buffer)
            if data.ndim > 1:
                data = data.mean(axis=1)
            if sr != 16000:
                ratio = 16000 / sr
                n_samples = int(len(data) * ratio)
                indices = np.linspace(0, len(data) - 1, n_samples).astype(int)
                data = data[indices]

            out = io.BytesIO()
            sf.write(out, data, 16000, format='WAV')
            return out.getvalue()
        except Exception as e:
            logger.warning(f"[WebUI] WAV 重采样失败，使用原始数据: {e}")
            return audio_bytes

    # 其他格式：使用 pydub 转换
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio = audio.set_channels(1).set_frame_rate(16000)
        out = io.BytesIO()
        audio.export(out, format='wav')
        wav_data = out.getvalue()
        logger.info(f"[WebUI] {audio_format} -> WAV 转换完成: {len(audio_bytes)} -> {len(wav_data)} bytes")
        return wav_data
    except Exception as e:
        logger.warning(f"[WebUI] pydub 转换失败，使用原始数据: {e}")
        return audio_bytes
