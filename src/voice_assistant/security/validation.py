"""
安全工具模块
提供输入验证、速率限制等安全功能
"""
import time
import threading
from functools import wraps
from typing import Callable, Any

# 安全常量
MAX_TEXT_LENGTH = 1000  # 最大文本输入长度
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 最大音频文件大小 (10MB)
MAX_ASR_CALLS_PER_MINUTE = 30  # 每分钟最大 ASR 调用次数
MAX_LLM_CALLS_PER_MINUTE = 20  # 每分钟最大 LLM 调用次数


class SecurityError(Exception):
    """安全相关错误"""
    pass


class RateLimitError(SecurityError):
    """速率限制错误"""
    pass


class InputValidationError(SecurityError):
    """输入验证错误"""
    pass


def validate_text_input(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """验证文本输入

    Args:
        text: 待验证的文本
        max_length: 最大允许长度

    Returns:
        验证后的文本

    Raises:
        InputValidationError: 输入验证失败
    """
    if not text:
        raise InputValidationError("输入不能为空")

    if len(text) > max_length:
        raise InputValidationError(f"输入过长，最大 {max_length} 字符")

    # 移除控制字符（保留换行和制表符）
    cleaned = ''.join(c for c in text if c.isprintable() or c in '\n\t')

    return cleaned.strip()


def validate_audio_input(audio_bytes: bytes, max_size: int = MAX_AUDIO_SIZE) -> bytes:
    """验证音频输入

    Args:
        audio_bytes: 音频数据字节
        max_size: 最大允许大小

    Returns:
        验证后的音频数据

    Raises:
        InputValidationError: 输入验证失败
    """
    if not audio_bytes:
        raise InputValidationError("音频数据不能为空")

    if len(audio_bytes) > max_size:
        raise InputValidationError(f"音频文件过大，最大 {max_size // 1024 // 1024}MB")

    return audio_bytes


def rate_limit(calls: int, period: float = 60.0) -> Callable:
    """速率限制装饰器

    Args:
        calls: 时间窗口内允许的最大调用次数
        period: 时间窗口（秒）

    Returns:
        装饰器函数

    Example:
        @rate_limit(calls=10, period=60)
        def my_api_call():
            ...
    """
    timestamps: list[float] = []

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            now = time.time()

            # 清理过期的调用记录
            timestamps[:] = [t for t in timestamps if now - t < period]

            if len(timestamps) >= calls:
                wait_time = period - (now - timestamps[0])
                raise RateLimitError(
                    f"请求过于频繁，请在 {wait_time:.1f} 秒后重试"
                )

            timestamps.append(now)
            return func(*args, **kwargs)

        return wrapper

    return decorator


class RateLimiter:
    """速率限制器类，用于更灵活的速率控制"""

    def __init__(self, calls: int, period: float = 60.0):
        """初始化速率限制器

        Args:
            calls: 时间窗口内允许的最大调用次数
            period: 时间窗口（秒）
        """
        self.calls = calls
        self.period = period
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def check(self) -> None:
        """检查是否允许调用（线程安全）

        Raises:
            RateLimitError: 超过速率限制
        """
        with self._lock:
            now = time.time()
            self._timestamps[:] = [t for t in self._timestamps if now - t < self.period]

            if len(self._timestamps) >= self.calls:
                wait_time = self.period - (now - self._timestamps[0])
                raise RateLimitError(
                    f"请求过于频繁，请在 {wait_time:.1f} 秒后重试"
                )

            self._timestamps.append(now)

    @property
    def remaining(self) -> int:
        """返回当前时间窗口内剩余的调用次数（线程安全）"""
        with self._lock:
            now = time.time()
            self._timestamps[:] = [t for t in self._timestamps if now - t < self.period]
            return max(0, self.calls - len(self._timestamps))


# 全局速率限制器实例
asr_limiter = RateLimiter(calls=MAX_ASR_CALLS_PER_MINUTE, period=60.0)
llm_limiter = RateLimiter(calls=MAX_LLM_CALLS_PER_MINUTE, period=60.0)