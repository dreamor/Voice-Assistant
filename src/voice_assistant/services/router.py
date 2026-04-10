"""
命令路由器服务
根据意图类型自动路由到对应的执行器
支持关键词匹配和 LLM 意图分类两种方式
"""
import json
import logging

import requests

from voice_assistant.config import config
from voice_assistant.executors.base import BaseExecutor
from voice_assistant.model.intent import Intent, IntentType

logger = logging.getLogger(__name__)

# 意图分类 prompt 模板
_INTENT_SYSTEM_PROMPT = """你是一个意图分类器。根据用户输入判断意图类型，返回 JSON 格式。

可选意图：
- computer_control: 用户想让电脑执行操作（打开/关闭程序、文件操作、系统设置、截屏、搜索等）
- query_answer: 用户询问事实性问题（天气、时间、计算、知识、翻译等）
- ordinary_chat: 闲聊、问候、情感交流、不需要执行操作的对话

用户输入: {user_text}

返回严格的 JSON 格式（不要包含其他内容）：
{{"intent_type": "computer_control", "confidence": 0.9}}"""


def llm_classify_intent(user_text: str) -> Intent | None:
    """使用云端 LLM 进行意图分类

    Args:
        user_text: 用户输入文本

    Returns:
        Intent 对象，LLM 调用失败时返回 None
    """
    intent_cfg = config.intent
    llm_cfg = config.llm

    try:
        response = requests.post(
            f"{llm_cfg.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {llm_cfg.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": intent_cfg.model,
                "messages": [{"role": "user", "content": _INTENT_SYSTEM_PROMPT.format(user_text=user_text)}],
                "max_tokens": 50,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=intent_cfg.timeout,
        )

        if response.status_code != 200:
            logger.warning(f"LLM 意图识别失败: HTTP {response.status_code}")
            return None

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return None

        # 解析 JSON 结果
        result = json.loads(content)
        intent_type_str = result.get("intent_type", "")
        confidence = float(result.get("confidence", 0.5))

        # 映射意图类型
        intent_type_map = {
            "computer_control": IntentType.COMPUTER_CONTROL,
            "query_answer": IntentType.QUERY_ANSWER,
            "ordinary_chat": IntentType.ORDINARY_CHAT,
        }
        intent_type = intent_type_map.get(intent_type_str)
        if intent_type is None:
            logger.warning(f"未知意图类型: {intent_type_str}")
            return None

        return Intent(
            intent_type=intent_type,
            original_text=user_text,
            confidence=confidence,
        )

    except requests.Timeout:
        logger.warning("LLM 意图识别超时")
        return None
    except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"LLM 意图识别异常: {e}")
        return None


def _keyword_classify_intent(user_text: str) -> Intent:
    """基于关键词的意图分类（LLM 不可用时的 fallback）"""
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


def simple_classify_intent(user_text: str) -> Intent:
    """意图分类：优先使用 LLM，失败时 fallback 到关键词匹配

    Args:
        user_text: 用户输入文本

    Returns:
        Intent 对象
    """
    result = llm_classify_intent(user_text)
    if result is not None and result.confidence >= 0.3:
        return result

    # Fallback to keyword matching
    return _keyword_classify_intent(user_text)


class CommandRouter:
    """命令路由器"""

    def __init__(self, executors: list[BaseExecutor]):
        """
        初始化路由器

        Args:
            executors: 执行器列表
        """
        self.executors = executors

    def route(self, intent: Intent, context: dict | None = None) -> dict:
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

    def _build_kwargs(self, intent: Intent, context: dict | None) -> dict:
        """根据意图类型构建执行参数"""
        kwargs = {'user_text': intent.original_text}

        if context:
            if 'history' in context:
                kwargs['conversation_history'] = context['history']
            if 'direct_response' in context:
                kwargs['direct_response'] = context['direct_response']

        return kwargs
