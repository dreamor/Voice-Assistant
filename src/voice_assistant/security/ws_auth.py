"""
WebSocket 认证模块

为 WebSocket 连接提供基于 HMAC 签名令牌的认证机制。
本地开发（localhost）默认跳过认证，非本地访问需要有效令牌。
"""
import hashlib
import hmac
import logging
import os
import time

logger = logging.getLogger(__name__)

# 令牌有效期（秒）
TOKEN_TTL = 300  # 5 分钟

# 是否启用认证（默认：非 localhost 启用）
AUTH_ENABLED = os.getenv("WS_AUTH_ENABLED", "").lower() in ("1", "true", "yes")

# HMAC 签名密钥（每次启动随机生成，也可通过环境变量固定）
_SECRET_KEY = os.getenv(
    "WS_AUTH_SECRET",
    os.urandom(32).hex(),
)


def generate_token(client_id: str) -> str:
    """为指定客户端生成认证令牌。

    令牌格式: timestamp.hmac_hex
    HMAC 输入: timestamp:client_id
    """
    timestamp = str(int(time.time()))
    payload = f"{timestamp}:{client_id}"
    signature = hmac.new(
        _SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{timestamp}.{signature}"


def verify_token(token: str, client_id: str) -> bool:
    """验证认证令牌是否有效。

    Args:
        token: 客户端提供的令牌
        client_id: 客户端标识

    Returns:
        True 如果令牌有效且未过期
    """
    if not token or "." not in token:
        return False

    parts = token.split(".", 1)
    if len(parts) != 2:
        return False

    timestamp_str, signature = parts

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False

    # 检查令牌是否过期
    if time.time() - timestamp > TOKEN_TTL:
        logger.warning(f"[WS-Auth] 令牌已过期: client_id={client_id}")
        return False

    # 验证 HMAC 签名
    payload = f"{timestamp_str}:{client_id}"
    expected = hmac.new(
        _SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        logger.warning(f"[WS-Auth] 签名验证失败: client_id={client_id}")
        return False

    return True


def is_auth_required(client_host: str | None) -> bool:
    """判断是否需要认证。

    本地访问（localhost/127.0.0.1）默认不需要认证，
    除非显式设置了 WS_AUTH_ENABLED=true。
    非本地访问默认需要认证，除非显式设置了 WS_AUTH_ENABLED=false。

    Args:
        client_host: 客户端主机地址

    Returns:
        True 如果需要认证
    """
    if AUTH_ENABLED:
        return True

    # 本地访问默认不需要认证
    if client_host and client_host in ("127.0.0.1", "::1", "localhost"):
        return False

    # 非本地访问默认需要认证
    return True
