"""
Open Interpreter 执行器
使用真正的 Open Interpreter 库实现电脑控制
"""
import logging
import os
from typing import Any, Optional

# 禁用 litellm 远程 cost map 获取（避免 SSL 警告）
os.environ["LITELLM_DROP_PARAMS"] = "true"
os.environ["LITELLM_MODEL_ALIASES"] = "{}"
os.environ["LITELLM_MAX_PARALLEL_REQUESTS"] = "0"

from voice_assistant.config import config
from voice_assistant.executors.base import BaseExecutor
from voice_assistant.model.intent import IntentType

logger = logging.getLogger(__name__)


class InterpreterExecutor(BaseExecutor):
    """Open Interpreter 执行器（符合 BaseExecutor 接口）"""

    def __init__(self, auto_run: bool = True, verbose: bool = False):
        """
        初始化 Open Interpreter

        Args:
            auto_run: 是否自动执行生成的代码（无需用户确认）
            verbose: 是否输出详细日志
        """
        self.auto_run = auto_run
        self.verbose = verbose
        self._interpreter = None

    def _get_interpreter(self):
        """懒加载 interpreter（避免未安装时报错）"""
        if self._interpreter is None:
            try:
                from interpreter import interpreter
                self._interpreter = interpreter

                # 配置 interpreter
                interpreter.auto_run = self.auto_run
                interpreter.verbose = self.verbose

                # 限制循环次数，防止无限重试（最多3次代码执行）
                interpreter.max_loops = 3

                # 配置 LLM
                llm_cfg = config.llm

                # 在线 API 配置
                # litellm 需要 openai/ 前缀表示 OpenAI 兼容 API
                interpreter.llm.model = f"openai/{llm_cfg.model}"
                interpreter.llm.api_key = llm_cfg.api_key
                interpreter.llm.api_base = llm_cfg.base_url

                # 设置 context_window 和 max_tokens 避免警告
                interpreter.llm.context_window = 32000
                interpreter.llm.max_tokens = 4096

            except Exception as e:
                logger.error(f"Open Interpreter 初始化失败: {e}")
                raise

        return self._interpreter

    def can_handle(self, intent_type: str) -> bool:
        """判断是否可以处理该意图类型"""
        return intent_type == IntentType.COMPUTER_CONTROL.value

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """执行电脑控制命令

        Args (via kwargs):
            user_text: 用户命令文本
            user_command: 备用命令文本

        Returns:
            {"success": bool, "response": str, "messages": list}
        """
        command = kwargs.get('user_text') or kwargs.get('user_command') or ""

        # 设置 UTF-8 编码
        import io
        import sys
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

        try:
            interp = self._get_interpreter()

            # 执行命令
            messages = interp.chat(command)

            # 提取响应文本
            response = self._extract_response(messages)

            return {
                "success": True,
                "response": response,
                "messages": messages
            }

        except ImportError as e:
            return {
                "success": False,
                "response": f"Open Interpreter 未安装：{e}",
                "messages": []
            }
        except Exception as e:
            logger.error(f"Open Interpreter 执行失败：{e}")
            return {
                "success": False,
                "response": f"执行失败：{e}",
                "messages": []
            }

    def _extract_response(self, messages: list) -> str:
        """从 Open Interpreter 消息中提取用户友好的响应"""
        if not messages:
            return "任务完成"

        for msg in messages:
            if msg.get("role") == "computer" and msg.get("type") == "console":
                content = msg.get("content", "")
                if content and "error" in content.lower():
                    return "执行失败"

        code_executed = False
        for msg in messages:
            if msg.get("role") == "computer" and msg.get("type") == "output":
                code_executed = True
                break
            if msg.get("role") == "computer" and msg.get("type") == "console":
                content = msg.get("content", "")
                if content:
                    code_executed = True
                    break

        if code_executed:
            return "任务完成"

        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("type") == "message":
                content = msg.get("content", "").strip()
                if content:
                    return content

        return "任务完成"

    def reset(self):
        """重置 interpreter 状态（开始新的对话）"""
        if self._interpreter:
            self._interpreter.messages = []
