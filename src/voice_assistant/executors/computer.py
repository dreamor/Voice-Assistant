"""
电脑控制执行器 - Open Interpreter 模式
"""
import logging
from typing import Any, Optional

from voice_assistant.executors.base import BaseExecutor
from voice_assistant.model.intent import IntentType

logger = logging.getLogger(__name__)


class ComputerExecutor(BaseExecutor):
    """电脑控制执行器（使用 Open Interpreter）"""

    def __init__(self, auto_run: bool = True, verbose: bool = False):
        """
        初始化电脑控制执行器

        Args:
            auto_run: 是否自动执行生成的代码
            verbose: 是否输出详细日志
        """
        self.auto_run = auto_run
        self.verbose = verbose
        self._executor = None

    def _get_executor(self):
        """懒加载执行器"""
        if self._executor is None:
            from voice_assistant.executors.interpreter import InterpreterExecutor
            self._executor = InterpreterExecutor(
                auto_run=self.auto_run,
                verbose=self.verbose
            )
        return self._executor

    def can_handle(self, intent_type: str) -> bool:
        return intent_type == IntentType.COMPUTER_CONTROL.value

    def execute(self, user_command: str, **kwargs) -> dict[str, Any]:
        """
        执行电脑控制命令

        Args:
            user_command: 用户命令文本

        Returns:
            {
                "success": bool,
                "response": str,
                "messages": list
            }
        """
        try:
            executor = self._get_executor()
            return executor.execute(user_command)
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