"""EventBus — 全局事件订阅/广播系统

与 Hook 系统（P0-2）互补：
- Hook: 工具执行的中间件管道，关注 before/after 拦截和修改
- EventBus: 全局广播，关注通知和订阅，不可拦截
"""
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EventName(str, Enum):
    """事件名称"""

    # Agent 生命周期
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"

    # 工具执行
    TOOL_BEFORE = "tool_before"
    TOOL_AFTER = "tool_after"

    # 消息
    MESSAGE_CREATED = "message_created"

    # 压缩
    COMPACT_START = "compact_start"
    COMPACT_END = "compact_end"

    # 错误
    ERROR = "error"


@dataclass
class Event:
    """事件对象"""

    name: EventName | str
    data: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False


# 事件处理器类型
EventHandler = Callable[[Event], None]


class EventBus:
    """全局事件总线

    用法:
        bus = EventBus()
        bus.on(EventName.TOOL_AFTER, lambda e: print(e.data))
        bus.emit(Event(EventName.TOOL_AFTER, data={"tool": "open_file", "success": True}))
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event: EventName | str, handler: EventHandler) -> None:
        """注册事件处理器"""
        key = event.value if isinstance(event, EventName) else event
        self._handlers[key].append(handler)

    def off(self, event: EventName | str, handler: EventHandler) -> None:
        """移除事件处理器"""
        key = event.value if isinstance(event, EventName) else event
        handlers = self._handlers.get(key, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event: Event) -> None:
        """广播事件到所有处理器"""
        key = event.name.value if isinstance(event.name, EventName) else event.name
        for handler in self._handlers.get(key, []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"[EventBus] 事件处理器异常 ({key}): {e}", exc_info=True)

    def clear(self) -> None:
        """清除所有处理器"""
        self._handlers.clear()


# 全局单例
_global_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局事件总线单例"""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus
