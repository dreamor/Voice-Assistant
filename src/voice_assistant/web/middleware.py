"""速率限制与中间件"""
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """简单的速率限制器"""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def check(self, client_id: str) -> bool:
        """检查是否超过限制"""
        now = time.time()
        self.requests[client_id] = [
            t for t in self.requests[client_id]
            if now - t < self.window_seconds
        ]

        if len(self.requests[client_id]) >= self.max_requests:
            return False

        self.requests[client_id].append(now)
        return True


rate_limiter = RateLimiter(max_requests=30, window_seconds=60)
