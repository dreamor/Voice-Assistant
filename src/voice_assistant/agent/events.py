"""
结构化事件流协议 - Agent 生命周期事件定义

借鉴 pi 的分层事件模型，提供比旧 AgentEvent 更丰富的事件类型，
使前端能精确感知 agent 处于哪个阶段，并携带完整的工具执行数据。
"""
import uuid
from dataclasses import dataclass, field
from enum import Enum


class EventType(str, Enum):
    """Agent 事件类型"""

    # Agent 生命周期
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"

    # Turn（一轮 LLM 调用）
    TURN_START = "turn_start"
    TURN_END = "turn_end"

    # 消息流
    MESSAGE_START = "message_start"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_END = "message_end"

    # 工具执行
    TOOL_CALL = "tool_call"
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_UPDATE = "tool_execution_update"
    TOOL_EXECUTION_END = "tool_execution_end"

    # 确认
    CONFIRM_REQUIRED = "confirm_required"

    # 错误/控制
    ERROR = "error"
    COMPACT = "compact"


@dataclass
class AgentEvent:
    """Agent 循环流式事件（v2）

    相比旧版增加了：
    - EventType enum 替代裸字符串
    - tool_call_id 关联工具调用的 start/end
    - duration_ms 工具执行耗时
    - display_hint 工具结果渲染提示
    - data 通用数据载荷
    - iteration 当前迭代轮次
    """

    type: EventType | str
    # 文本内容（MESSAGE_DELTA / ERROR）
    content: str | None = None
    # 工具相关
    tool_name: str | None = None
    tool_arguments: dict | None = None
    tool_call_id: str | None = None
    tool_result: str | None = None
    tool_result_data: dict | None = None
    tool_display_hint: str = "text"
    tool_success: bool | None = None
    duration_ms: int | None = None
    # 确认相关
    confirm_id: str | None = None
    confirm_message: str | None = None
    confirm_level: str | None = None
    # 通用
    iteration: int = 0
    data: dict = field(default_factory=dict)
    # 最终结果（仅 complete/agent_end）
    result: "AgentResult | None" = None

    def to_ws_message(self) -> dict:
        """转换为 WebSocket 消息格式"""
        msg: dict = {"type": self.type if isinstance(self.type, str) else self.type.value}

        if self.content is not None:
            msg["content"] = self.content
        if self.tool_name is not None:
            msg["tool_name"] = self.tool_name
        if self.tool_arguments is not None:
            msg["tool_arguments"] = self.tool_arguments
        if self.tool_call_id is not None:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_result is not None:
            msg["tool_result"] = self.tool_result
        if self.tool_result_data is not None:
            msg["tool_result_data"] = self.tool_result_data
        if self.tool_display_hint != "text":
            msg["display_hint"] = self.tool_display_hint
        if self.tool_success is not None:
            msg["success"] = self.tool_success
        if self.duration_ms is not None:
            msg["duration_ms"] = self.duration_ms
        if self.confirm_id is not None:
            msg["confirm_id"] = self.confirm_id
        if self.confirm_message is not None:
            msg["message"] = self.confirm_message
        if self.confirm_level is not None:
            msg["level"] = self.confirm_level
        if self.iteration > 0:
            msg["iteration"] = self.iteration
        if self.data:
            msg["data"] = self.data
        if self.result is not None:
            msg["result"] = {
                "success": self.result.success,
                "response": self.result.response,
                "tool_calls_made": self.result.tool_calls_made,
                "iterations": self.result.iterations,
            }
        return msg


@dataclass
class AgentResult:
    """Agent 循环最终结果"""
    success: bool
    response: str
    tool_calls_made: list[str] = field(default_factory=list)
    confirmations_needed: list = field(default_factory=list)
    iterations: int = 0
    fallback_used: bool = False


def new_call_id() -> str:
    """生成工具调用 ID"""
    return f"call_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# 向后兼容：旧事件类型字符串 → EventType 映射
# ---------------------------------------------------------------------------
_LEGACY_TYPE_MAP = {
    "llm_token": EventType.MESSAGE_DELTA,
    "tool_start": EventType.TOOL_EXECUTION_START,
    "tool_result": EventType.TOOL_EXECUTION_END,
    "complete": EventType.AGENT_END,
    "error": EventType.ERROR,
}


def normalize_event_type(event_type: str) -> EventType:
    """将旧事件类型字符串转换为 EventType enum"""
    if isinstance(event_type, EventType):
        return event_type
    if event_type in _LEGACY_TYPE_MAP:
        return _LEGACY_TYPE_MAP[event_type]
    return EventType(event_type)
