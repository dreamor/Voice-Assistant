"""
FunASR 本地语音识别引擎
使用 Paraformer + FSMN-VAD + CT-Transformer  pipeline
"""
import io
import logging
import tempfile
import wave
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from funasr import AutoModel
    FUNASR_AVAILABLE = True
except ImportError:
    FUNASR_AVAILABLE = False
    AutoModel = None  # type: ignore


class FunASRError(Exception):
    """FunASR 错误"""
    pass


class FunASREngine:
    """FunASR 语音识别引擎"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
        vad_threshold: float = 0.5,
        vad_max_single_segment_time: int = 6000,
        disable_pbar: bool = True,
    ):
        """
        初始化 FunASR 引擎

        Args:
            model_path: 模型路径（可选，None 时自动下载）
            device: 设备 (cpu/cuda)
            vad_threshold: VAD 阈值
            vad_max_single_segment_time: VAD 最大单段时间（毫秒）
            disable_pbar: 是否禁用进度条
        """
        if not FUNASR_AVAILABLE:
            raise FunASRError("FunASR 未安装，请运行: pip install funasr modelscope torch torchaudio librosa")

        self.device = device
        self._vad_threshold = vad_threshold
        self._vad_max_single_segment_time = vad_max_single_segment_time
        self._disable_pbar = disable_pbar
        self._model = None

        self._init_model(vad_threshold, vad_max_single_segment_time, disable_pbar)

    def _init_model(self, vad_threshold, vad_max_single_segment_time, disable_pbar):
        """初始化模型"""
        self._model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            device=self.device,
            disable_pbar=disable_pbar,
            vad_kwargs={
                "threshold": vad_threshold,
                "max_single_segment_time": vad_max_single_segment_time,
            },
        )
        logger.info(f"FunASR 模型初始化成功 (device={self.device})")

    def recognize(self, audio_path: str, hotwords: Optional[str] = None) -> str:
        """
        识别音频文件

        Args:
            audio_path: 音频文件路径
            hotwords: 热词（可选），格式: "热词1 热词2"

        Returns:
            识别结果文本
        """
        if self._model is None:
            raise FunASRError("FunASR 模型未初始化")

        kwargs = {}
        if hotwords:
            kwargs["hotword"] = hotwords

        result = self._model.generate(
            input=audio_path,
            batch_size_s=300,
            **kwargs,
        )

        if result and len(result) > 0:
            text = result[0].get("text", "").strip()
            return text

        return ""

    def recognize_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        hotwords: Optional[str] = None,
    ) -> str:
        """
        识别音频字节流

        Args:
            audio_bytes: 音频字节数据（WAV 格式）
            sample_rate: 采样率
            hotwords: 热词

        Returns:
            识别结果文本
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return self.recognize(tmp_path, hotwords=hotwords)
        finally:
            import os
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def close(self):
        """释放模型资源"""
        self._model = None
        logger.info("FunASR 模型已释放")


class FunASRClient:
    """FunASR 客户端（兼容云端 ASR 接口）"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
        vad_threshold: float = 0.5,
    ):
        """
        初始化 FunASR 客户端

        Args:
            model_path: 模型路径
            device: 设备
            vad_threshold: VAD 阈值
        """
        self._engine = FunASREngine(
            model_path=model_path,
            device=device,
            vad_threshold=vad_threshold,
        )

    def recognize(self, audio_path: str, hotwords: Optional[str] = None) -> str:
        """识别音频文件"""
        return self._engine.recognize(audio_path, hotwords=hotwords)

    def recognize_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        hotwords: Optional[str] = None,
    ) -> str:
        """识别音频字节流"""
        return self._engine.recognize_bytes(audio_bytes, sample_rate=sample_rate, hotwords=hotwords)

    def close(self):
        """关闭客户端"""
        self._engine.close()
