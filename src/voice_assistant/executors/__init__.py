"""执行器模块"""

from voice_assistant.executors.base import BaseExecutor
from voice_assistant.executors.chat import ChatExecutor
from voice_assistant.executors.computer import ComputerExecutor
from voice_assistant.executors.interpreter import InterpreterExecutor

# 执行器注册表：意图类型 → 执行器类
EXECUTOR_REGISTRY: dict[str, type[BaseExecutor]] = {
    "computer_control": ComputerExecutor,
    "ordinary_chat": ChatExecutor,
    "query_answer": ChatExecutor,
}


def get_executor_for_intent(intent_type: str) -> type[BaseExecutor] | None:
    """根据意图类型获取执行器类"""
    return EXECUTOR_REGISTRY.get(intent_type)


def register_executor(intent_type: str, executor_class: type[BaseExecutor]) -> None:
    """注册自定义执行器"""
    EXECUTOR_REGISTRY[intent_type] = executor_class


__all__ = [
    'BaseExecutor',
    'ChatExecutor',
    'ComputerExecutor',
    'InterpreterExecutor',
    'EXECUTOR_REGISTRY',
    'get_executor_for_intent',
    'register_executor',
]
