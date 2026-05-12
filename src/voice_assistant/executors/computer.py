"""
电脑控制执行器
委托给 InterpreterExecutor 处理电脑操作类意图
"""
import logging
from typing import Any

from voice_assistant.executors.base import BaseExecutor
from voice_assistant.executors.interpreter import InterpreterExecutor
from voice_assistant.model.intent import IntentType

logger = logging.getLogger(__name__)


class ComputerExecutor(BaseExecutor):
    """电脑控制执行器（委托给 InterpreterExecutor）"""

    def __init__(self, auto_run: bool = True, verbose: bool = False):
        self.auto_run = auto_run
        self.verbose = verbose
        self._executor: InterpreterExecutor | None = None

    def _get_executor(self) -> InterpreterExecutor:
        """懒加载执行器"""
        if self._executor is None:
            self._executor = InterpreterExecutor(
                auto_run=self.auto_run,
                verbose=self.verbose
            )
        return self._executor

    def can_handle(self, intent_type: str) -> bool:
        return intent_type == IntentType.COMPUTER_CONTROL.value

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """执行电脑控制命令（委托给 InterpreterExecutor）"""
        try:
            executor = self._get_executor()
            return executor.execute(**kwargs)
        except Exception as e:
            logger.error(f"ComputerExecutor 执行失败：{e}")
            return {
                "success": False,
                "response": f"执行失败：{e}",
                "messages": []
            }

    def reset(self):
        """重置执行器状态"""
        if self._executor:
            self._executor.reset()
