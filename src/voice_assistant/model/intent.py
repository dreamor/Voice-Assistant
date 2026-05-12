"""
意图识别结果数据类
定义 LLM 和执行器之间的标准接口
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any


class IntentType(Enum):
    """意图类型"""
    COMPUTER_CONTROL = "computer_control"  # 电脑操作（Open Interpreter）
    ORDINARY_CHAT = "ordinary_chat"        # 普通对话
    QUERY_ANSWER = "query_answer"          # 问答查询


@dataclass(frozen=True)
class Intent:
    """意图表示"""
    intent_type: IntentType
    original_text: str                          # 用户原始输入
    slots: dict[str, Any] = field(default_factory=dict)  # 槽位信息
    confidence: float = 1.0                     # 置信度

    # 电脑控制特有（Open Interpreter）
    code_to_execute: Optional[str] = None
    language: Optional[str] = None

@dataclass
class ExecutorResult:
    """执行器结果数据类
    
    统一所有执行器的返回类型，替代 dict[str, Any]。
    """
    success: bool
    response: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    history_updated: list | None = None
    messages: list | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（向后兼容）"""
        result = {"success": self.success, "response": self.response}
        if self.history_updated is not None:
            result["history_updated"] = self.history_updated
        if self.messages is not None:
            result["messages"] = self.messages
        result.update(self.data)
        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExecutorResult":
        """从字典创建（向后兼容）"""
        return cls(
            success=d.get("success", False),
            response=d.get("response", ""),
            data={k: v for k, v in d.items() if k not in ("success", "response", "history_updated", "messages")},
            history_updated=d.get("history_updated"),
            messages=d.get("messages"),
        )
