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