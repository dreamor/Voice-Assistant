"""
ASR 提供者协议与工厂
定义语音识别的标准接口，支持云端和本地 ASR 的统一切换
"""
import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ASRProvider(Protocol):
    """语音识别提供者协议
    
    所有 ASR 后端（云端/本地）都必须实现此协议，
    使 main.py 不再需要 if/else 切换。
    """

    def recognize_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """从音频字节数据识别文本

        Args:
            audio_bytes: 音频数据（WAV 格式或原始 PCM）
            sample_rate: 采样率

        Returns:
            识别的文本，识别失败返回空字符串
        """
        ...

    def close(self) -> None:
        """释放资源"""
        ...


def create_asr_provider(config) -> ASRProvider:
    """根据配置创建 ASR 提供者

    Args:
        config: AppConfig 配置对象

    Returns:
        ASRProvider 实例
    """
    if config.asr.use_local:
        try:
            from voice_assistant.audio.funasr_asr import FunASRClient, FUNASR_AVAILABLE
            if FUNASR_AVAILABLE:
                provider = FunASRClient(
                    model_path=config.asr.local.model_path,
                    device=config.asr.local.device,
                    vad_threshold=config.asr.local.vad_threshold,
                )
                logger.info("ASR 提供者: 本地 FunASR")
                return provider
            else:
                logger.warning("FunASR 未安装，回退到云端 ASR")
        except Exception as e:
            logger.warning(f"FunASR 初始化失败: {e}，回退到云端 ASR")

    # 云端 ASR（默认）
    from voice_assistant.audio.cloud_asr import CloudASR
    provider = CloudASR(
        api_key=config.asr.api_key,
        model=config.asr.model
    )
    logger.info(f"ASR 提供者: 云端 {config.asr.model}")
    return provider
