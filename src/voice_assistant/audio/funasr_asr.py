"""
FunASR 本地语音识别模块
使用 FunASR 的 Paraformer + FSMN-VAD + CT-Transformer 流水线进行本地 ASR
参考: https://github.com/modelscope/FunASR
"""
import logging
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# FunASR 可选依赖
try:
    from funasr import AutoModel
    FUNASR_AVAILABLE = True
except ImportError:
    AutoModel = None  # type: ignore[misc,assignment]
    FUNASR_AVAILABLE = False
    logger.warning("FunASR 未安装，本地 ASR 功能不可用。请运行: pip install funasr")


class FunASRError(Exception):
    """FunASR 错误"""
    pass


class FunASREngine:
    """FunASR 本地语音识别引擎

    使用 Paraformer-large 进行语音识别，FSMN-VAD 进行语音活动检测，
    CT-Transformer 进行标点符号预测。所有模型在本地运行。
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
        vad_threshold: float = 0.5,
        vad_max_single_segment_time: int = 6000,
        disable_pbar: bool = True,
    ):
        """初始化 FunASR 引擎

        Args:
            model_path: 本地模型路径（可选，默认从 modelscope 下载）
            device: 推理设备 ("cpu" 或 "cuda")
            vad_threshold: VAD 阈值
            vad_max_single_segment_time: VAD 最大单段时长（毫秒）
            disable_pbar: 是否禁用进度条

        Raises:
            FunASRError: 初始化失败
        """
        if not FUNASR_AVAILABLE:
            raise FunASRError("FunASR 未安装")

        self.device = device
        self.model_path = model_path
        self._model = None

        self._init_model(
            vad_threshold=vad_threshold,
            vad_max_single_segment_time=vad_max_single_segment_time,
            disable_pbar=disable_pbar,
        )

    def _init_model(
        self,
        vad_threshold: float,
        vad_max_single_segment_time: int,
        disable_pbar: bool,
    ):
        """初始化 FunASR AutoModel

        AutoModel 会自动加载 Paraformer、FSMN-VAD 和 CT-Transformer。
        """
        try:
            self._model = AutoModel(
                model="paraformer-zh",
                vad_model="fsmn-vad",
                punc_model="ct-punc",
                device=self.device,
                vad_kwargs={
                    "threshold": vad_threshold,
                    "max_single_segment_time": vad_max_single_segment_time,
                },
                disable_pbar=disable_pbar,
                disable_log=True,
            )
            logger.info(f"FunASR 引擎初始化成功 (device={self.device})")
            if self.model_path:
                logger.info(f"  模型路径: {self.model_path}")

        except Exception as e:
            raise FunASRError(f"FunASR 引擎初始化失败: {e}")

    def recognize(self, audio_path: str, hotwords: Optional[list[str]] = None) -> str:
        """从音频文件识别

        Args:
            audio_path: WAV 音频文件路径
            hotwords: 热词列表（可选）

        Returns:
            识别的文本

        Raises:
            FunASRError: 识别失败
        """
        if self._model is None:
            raise FunASRError("FunASR 引擎未初始化")

        try:
            kwargs = {}
            if hotwords:
                kwargs["hotword"] = " ".join(hotwords)

            result = self._model.generate(
                input=audio_path,
                batch_size_s=300,
                **kwargs,
            )

            if not result:
                return ""

            # FunASR 返回 list[dict]，提取文本
            text = result[0].get("text", "") if isinstance(result, list) else result.get("text", "")
            return text.strip()

        except Exception as e:
            logger.error(f"FunASR 识别失败: {e}")
            raise FunASRError(f"识别失败: {e}")

    def recognize_bytes(
        self, audio_bytes: bytes, sample_rate: int = 16000,
        hotwords: Optional[list[str]] = None,
    ) -> str:
        """从音频字节识别

        Args:
            audio_bytes: 音频数据（WAV 格式或原始 PCM）
            sample_rate: 采样率
            hotwords: 热词列表（可选）

        Returns:
            识别的文本
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # 如果是 WAV 格式，直接写入
            if audio_bytes[:4] == b"RIFF":
                with open(tmp_path, "wb") as f:
                    f.write(audio_bytes)
            else:
                # 原始 PCM 数据，转换为 WAV
                try:
                    audio_data = np.frombuffer(audio_bytes, dtype=np.float32)
                    if audio_data.size > 0 and audio_data.max() <= 1.0:
                        audio_data = (audio_data * 32767).astype(np.int16)
                except (ValueError, TypeError):
                    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                sf.write(tmp_path, audio_data, sample_rate, format="WAV")

            return self.recognize(tmp_path, hotwords=hotwords)

        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

    def close(self):
        """关闭引擎，释放资源"""
        self._model = None
        logger.debug("FunASR 引擎已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class FunASRClient:
    """FunASR 客户端包装器，提供简化的接口"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
        vad_threshold: float = 0.5,
    ):
        """初始化客户端

        Args:
            model_path: 本地模型路径（可选）
            device: 推理设备
            vad_threshold: VAD 阈值
        """
        self._engine: Optional[FunASREngine] = None
        self.model_path = model_path
        self.device = device
        self.vad_threshold = vad_threshold

    def _ensure_engine(self) -> FunASREngine:
        """确保引擎已初始化"""
        if self._engine is None:
            self._engine = FunASREngine(
                model_path=self.model_path,
                device=self.device,
                vad_threshold=self.vad_threshold,
            )
        return self._engine

    def recognize(self, audio_path: str, hotwords: Optional[list[str]] = None) -> str:
        """识别音频文件"""
        engine = self._ensure_engine()
        return engine.recognize(audio_path, hotwords=hotwords)

    def recognize_bytes(
        self, audio_bytes: bytes, sample_rate: int = 16000,
        hotwords: Optional[list[str]] = None,
    ) -> str:
        """识别音频字节"""
        engine = self._ensure_engine()
        return engine.recognize_bytes(audio_bytes, sample_rate, hotwords=hotwords)

    def close(self):
        """关闭客户端"""
        if self._engine:
            self._engine.close()
            self._engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def download_funasr_models(output_dir: str = "models/funasr") -> str:
    """下载 FunASR 模型

    Args:
        output_dir: 输出目录

    Returns:
        模型目录路径
    """
    if not FUNASR_AVAILABLE:
        raise FunASRError("FunASR 未安装")

    model_dir = Path(output_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"正在下载 FunASR 模型到 {model_dir}...")

    try:
        # 通过 AutoModel 初始化触发模型下载
        _ = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            disable_pbar=False,
        )
        logger.info("FunASR 模型下载完成")
        return str(model_dir)
    except Exception as e:
        logger.error(f"FunASR 模型下载失败: {e}")
        raise FunASRError(f"模型下载失败: {e}")
