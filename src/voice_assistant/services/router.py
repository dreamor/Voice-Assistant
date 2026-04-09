"""
命令路由器服务
根据意图类型自动路由到对应的执行器
"""
import logging
from typing import Any, Optional

from voice_assistant.models.intent import Intent, IntentType
from voice_assistant.executors.base import BaseExecutor

logger = logging.getLogger(__name__)


class CommandRouter:
    """命令路由器"""

    def __init__(self, executors: list[BaseExecutor]):
        """
        初始化路由器

        Args:
            executors: 执行器列表
        """
        self.executors = executors

    def route(self, intent: Intent, context: Optional[dict] = None) -> dict[str, Any]:
        """
        根据意图路由到对应的执行器

        Args:
            intent: 意图对象
            context: 执行上下文（如对话历史）

        Returns:
            执行结果
        """
        for executor in self.executors:
            if executor.can_handle(intent.intent_type.value):
                kwargs = self._build_kwargs(intent, context)
                return executor.execute(**kwargs)

        # fallback 到普通对话
        logger.warning(f"未匹配的意图类型：{intent.intent_type}")
        return {"success": True, "response": "抱歉，我没有理解您的意思。"}

    def _build_kwargs(self, intent: Intent, context: Optional[dict]) -> dict:
        """根据意图类型构建执行参数"""
        kwargs = {'user_text': intent.original_text}

        if context:
            if 'history' in context:
                kwargs['conversation_history'] = context['history']

        return kwargs


def simple_classify_intent(user_text: str) -> Intent:
    """
    简单的意图分类（基于关键词）

    Args:
        user_text: 用户输入文本

    Returns:
        Intent 对象
    """
    # 电脑操作关键词
    computer_keywords = [
        "打开", "关闭", "创建", "删除", "截屏", "截图", "新建",
        "运行", "执行", "启动", "停止", "复制", "移动", "重命名",
        "搜索", "查找", "下载", "上传", "安装", "卸载", "控制", "操作"
    ]

    for kw in computer_keywords:
        if kw in user_text:
            return Intent(
                intent_type=IntentType.COMPUTER_CONTROL,
                original_text=user_text,
                confidence=0.7
            )

    # 问句判断
    if any(c in user_text for c in "？?"):
        return Intent(
            intent_type=IntentType.QUERY_ANSWER,
            original_text=user_text,
            confidence=0.6
        )

    # 默认普通对话
    return Intent(
        intent_type=IntentType.ORDINARY_CHAT,
        original_text=user_text,
        confidence=0.5
    )