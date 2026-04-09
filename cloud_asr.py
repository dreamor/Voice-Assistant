"""
云端ASR模块 - 阿里云Paraformer实时语音识别
"""
import os
import tempfile
from http import HTTPStatus
import dashscope
from dashscope.audio.asr import Recognition
from config import config


class CloudASR:
    """云端语音识别类"""

    def __init__(self, api_key=None, model=None):
        """初始化云端ASR"""
        asr_cfg = config.asr
        self.api_key = api_key or asr_cfg.api_key
        self.model = model or asr_cfg.model
        self.base_url = asr_cfg.base_url
        dashscope.api_key = self.api_key
        dashscope.base_http_api_url = self.base_url

    def recognize_from_file(self, audio_file_path, sample_rate=None):
        """从音频文件识别

        Args:
            audio_file_path: WAV文件路径
            sample_rate: 音频采样率，默认从配置读取

        Returns:
            识别的文本，如果识别失败返回错误信息
        """
        if sample_rate is None:
            sample_rate = config.audio.sample_rate

        try:
            recognition = Recognition(
                model=self.model,
                format='wav',
                sample_rate=sample_rate,
                language_hints=['zh', 'en']
            )

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

    def recognize_from_bytes(self, audio_bytes, sample_rate=None):
        """从音频字节数据识别

        Args:
            audio_bytes: 音频数据（可以是WAV格式或原始PCM数据）
            sample_rate: 采样率，默认从配置读取

        Returns:
            识别的文本，如果识别失败返回错误信息
        """
        import soundfile as sf
        import numpy as np

        if sample_rate is None:
            sample_rate = config.audio.sample_rate

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


if __name__ == "__main__":
    asr = CloudASR()
    print("CloudASR 配置:")
    print(f"  Model: {asr.model}")
    print(f"  Base URL: {asr.base_url}")