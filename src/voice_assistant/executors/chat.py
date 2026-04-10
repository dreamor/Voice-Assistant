"""
对话执行器 - 处理普通聊天和问答
"""
import logging
from typing import Any

from voice_assistant.executors.base import BaseExecutor
from voice_assistant.model.intent import IntentType

logger = logging.getLogger(__name__)


class ChatExecutor(BaseExecutor):
    """对话执行器"""

    def __init__(self, max_response_length: int = 200, use_local: bool = False):
        self.max_response_length = max_response_length
        self._use_local = use_local

    def can_handle(self, intent_type: str) -> bool:
        return intent_type in [
            IntentType.ORDINARY_CHAT.value,
            IntentType.QUERY_ANSWER.value
        ]

    def execute(self, user_text: str,
                conversation_history: list | None = None,
                **kwargs) -> dict[str, Any]:
        """
        执行对话

        Args:
            user_text: 用户输入文本
            conversation_history: 对话历史记录

        Returns:
            {
                "success": bool,
                "response": str,
                "history_updated": list
            }
        """
        try:
            from voice_assistant.core.ai_client import ask_ai_stream

            history = conversation_history or self._conversation_history

            # 流式获取响应
            response = ""
            for partial in ask_ai_stream(user_text, history, use_local=self._use_local):
                response = partial

            # 限制长度
            if len(response) > self.max_response_length:
                response = response[:self.max_response_length] + "..."

            # 更新历史
            updated_history = self._update_history(
                history=history,
                user_text=user_text,
                response=response
            )

            self._conversation_history = updated_history

            return {
                "success": True,
                "response": response,
                "history_updated": updated_history
            }

        except Exception as e:
            logger.error(f"ChatExecutor 执行失败：{e}")
            return {
                "success": False,
                "response": f"抱歉，发生错误：{e}",
                "history_updated": conversation_history or []
            }

    def _update_history(self, history: list, user_text: str,
                        response: str, max_turns: int = 20) -> list:
        """更新对话历史"""
        history = history or []
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": response})

        # 限制长度
        if len(history) > max_turns:
            history = history[-max_turns:]

        return history

    def clear_history(self):
        """清空对话历史"""
        self._conversation_history.clear()

    def get_history(self) -> list:
        """获取对话历史"""
        return self._conversation_history.copy()
