"""
LLM 调用重试模块

提供错误分类、指数退避和重试策略，替代 llm_client.py 中的内联重试逻辑。
"""
import enum
import logging
import random
import time
from dataclasses import dataclass

import litellm

logger = logging.getLogger(__name__)


class ErrorClass(enum.Enum):
    """LLM 调用错误分类"""
    RATE_LIMIT = "rate_limit"      # 429 限流
    TIMEOUT = "timeout"            # 请求超时
    CONNECTION = "connection"      # 网络连接失败
    SERVER_ERROR = "server_error"  # 5xx 服务端错误
    CLIENT_ERROR = "client_error"  # 4xx 客户端错误（不重试）
    UNKNOWN = "unknown"            # 未知错误


@dataclass
class RetryPolicy:
    """重试策略配置"""
    max_retries: int = 3           # 单个模型最大重试次数
    base_delay: float = 1.0       # 基础延迟（秒）
    max_delay: float = 30.0       # 最大延迟（秒）
    backoff_factor: float = 2.0   # 退避倍数
    jitter: float = 0.1           # 抖动比例（0-1）


# 默认策略
DEFAULT_RETRY_POLICY = RetryPolicy()


def classify_error(exc: Exception) -> ErrorClass:
    """将 litellm 异常分类为 ErrorClass。

    Args:
        exc: litellm 抛出的异常

    Returns:
        错误分类
    """
    if isinstance(exc, litellm.RateLimitError):
        return ErrorClass.RATE_LIMIT
    if isinstance(exc, litellm.Timeout):
        return ErrorClass.TIMEOUT
    if isinstance(exc, litellm.APIConnectionError):
        return ErrorClass.CONNECTION

    # 检查状态码
    status_code = getattr(exc, "status_code", None)
    if status_code:
        if status_code == 429:
            return ErrorClass.RATE_LIMIT
        if 500 <= status_code < 600:
            return ErrorClass.SERVER_ERROR
        if 400 <= status_code < 500:
            return ErrorClass.CLIENT_ERROR

    if isinstance(exc, litellm.APIError):
        return ErrorClass.SERVER_ERROR

    return ErrorClass.UNKNOWN


def should_retry(error_class: ErrorClass) -> bool:
    """判断该错误类型是否应该重试。"""
    return error_class in (
        ErrorClass.RATE_LIMIT,
        ErrorClass.TIMEOUT,
        ErrorClass.CONNECTION,
        ErrorClass.SERVER_ERROR,
    )


def compute_delay(
    attempt: int,
    policy: RetryPolicy,
    error_class: ErrorClass,
    retry_after: float | None = None,
) -> float:
    """计算退避延迟时间。

    Args:
        attempt: 当前重试次数（从 0 开始）
        policy: 重试策略
        error_class: 错误分类
        retry_after: 服务器返回的 Retry-After 值（秒）

    Returns:
        延迟秒数
    """
    # 429 优先使用 Retry-After 头
    if error_class == ErrorClass.RATE_LIMIT and retry_after is not None:
        return min(retry_after, policy.max_delay)

    # 指数退避 + 抖动
    delay = policy.base_delay * (policy.backoff_factor ** attempt)
    jitter_amount = delay * policy.jitter
    delay += random.uniform(-jitter_amount, jitter_amount)
    return min(max(delay, 0), policy.max_delay)


def get_retry_after(exc: Exception) -> float | None:
    """从异常中提取 Retry-After 头值。"""
    headers = getattr(exc, "response", None)
    if headers is None:
        return None
    headers = getattr(headers, "headers", None)
    if headers is None:
        return None

    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if retry_after is None:
        return None

    try:
        return float(retry_after)
    except (ValueError, TypeError):
        return None
