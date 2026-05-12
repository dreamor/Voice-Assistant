"""
ASR 提供者协议与工厂
定义语音识别的标准接口，支持云端和本地 ASR 的统一切换
"""
import logging
from typing import Protocol, runtime_checkable, Dict, Type, Optional

logger = logging.getLogger(__name__)


@runtime_checkable
class ASRProvider(Protocol):
    """语音识别提供者协议

    所有 ASR 后端（云端/本地）都必须实现此协议，
    使上层代码不再需要 if/else 切换。

    可选方法：
    - recognize_stream(): 流式识别，不支持时应抛出 NotImplementedError
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


# ---------------------------------------------------------------------------
# ASR Provider 注册表
# ---------------------------------------------------------------------------

_ASR_REGISTRY: Dict[str, Type] = {}


def register_asr_provider(name: str, cls: Type) -> None:
    """注册 ASR 提供者

    Args:
        name: 提供者名称（如 "cloud", "local", "whisper"）
        cls: 实现 ASRProvider 协议的类

    Raises:
        TypeError: cls 不是类
    """
    if not isinstance(cls, type):
        raise TypeError(f"ASR 提供者必须是类，收到 {type(cls)}")
    if name in _ASR_REGISTRY:
        logger.warning(f"ASR 提供者 '{name}' 已存在，将被覆盖")
    _ASR_REGISTRY[name] = cls
    logger.debug(f"注册 ASR 提供者: {name}")


def create_asr_provider(config) -> ASRProvider:
    """根据配置创建 ASR 提供者

    Args:
        config: AppConfig 配置对象

    Returns:
        ASRProvider 实例

    Raises:
        ValueError: 未知的 ASR 提供者名称
    """
    # 确定提供者名称
    if config.asr.use_local:
        provider_name = "local"
    else:
        provider_name = "cloud"

    # 本地 ASR 特殊处理：需要检查 FunASR 是否可用
    if provider_name == "local":
        try:
            from voice_assistant.audio.funasr_asr import FUNASR_AVAILABLE
            if not FUNASR_AVAILABLE:
                logger.warning("FunASR 未安装，回退到云端 ASR")
                provider_name = "cloud"
        except Exception as e:
            logger.warning(f"FunASR 检查失败: {e}，回退到云端 ASR")
            provider_name = "cloud"

    if provider_name not in _ASR_REGISTRY:
        available = ", ".join(_ASR_REGISTRY.keys()) or "(无)"
        raise ValueError(
            f"未知的 ASR 提供者: '{provider_name}'，可用提供者: {available}"
        )

    cls = _ASR_REGISTRY[provider_name]

    # 根据提供者类型初始化
    if provider_name == "cloud":
        provider = cls(
            api_key=config.asr.api_key,
            model=config.asr.model,
        )
    elif provider_name == "local":
        provider = cls(
            model_path=config.asr.local.model_path,
            device=config.asr.local.device,
            vad_threshold=config.asr.local.vad_threshold,
        )
    else:
        provider = cls()

    logger.info(f"ASR 提供者: {provider_name}")
    return provider


# ---------------------------------------------------------------------------
# 默认注册
# ---------------------------------------------------------------------------

def _register_defaults():
    """注册默认的 ASR 提供者"""
    # 云端 ASR
    try:
        from voice_assistant.audio.cloud_asr import CloudASR
        register_asr_provider("cloud", CloudASR)
    except ImportError:
        logger.debug("CloudASR 不可用")

    # 本地 FunASR
    try:
        from voice_assistant.audio.funasr_asr import FunASRClient
        register_asr_provider("local", FunASRClient)
    except ImportError:
        logger.debug("FunASRClient 不可用")


_register_defaults()