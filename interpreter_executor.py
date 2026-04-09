"""
Open Interpreter 执行器
使用真正的 Open Interpreter 库实现电脑控制
支持在线和本地模型
"""
import logging
from typing import Optional

from config import config

logger = logging.getLogger(__name__)


class InterpreterExecutor:
    """Open Interpreter 执行器"""

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
        self._use_local = config.llm.use_local

    def _get_interpreter(self):
        """懒加载 interpreter（避免未安装时报错）"""
        if self._interpreter is None:
            try:
                from interpreter import interpreter
                self._interpreter = interpreter

                # 配置 interpreter
                interpreter.auto_run = self.auto_run
                interpreter.verbose = self.verbose

                # 配置 LLM
                llm_cfg = config.llm

                if llm_cfg.use_local:
                    # 本地模型配置
                    # Open Interpreter 需要通过本地服务器或特殊配置使用本地模型
                    # 这里我们使用自定义的本地 LLM 包装器
                    self._configure_local_llm(interpreter, llm_cfg)
                else:
                    # 在线 API 配置
                    # litellm 需要 openai/ 前缀表示 OpenAI 兼容 API
                    interpreter.llm.model = f"openai/{llm_cfg.model}"
                    interpreter.llm.api_key = llm_cfg.api_key
                    interpreter.llm.api_base = llm_cfg.base_url

            except ImportError:
                logger.error("Open Interpreter 未安装，请运行：pip install open-interpreter")
                raise

        return self._interpreter

    def _configure_local_llm(self, interpreter, llm_cfg):
        """配置本地 LLM

        Open Interpreter 通过 litellm 支持 OpenAI 兼容 API。
        对于本地模型，我们需要启动一个本地服务器或使用自定义 LLM 类。

        当前实现：使用本地 OpenAI 兼容服务器（如果可用）
        未来：直接集成 LiteRT-LM
        """
        logger.info(f"配置本地模型: {llm_cfg.local.model_name}")

        # 检查是否有本地 OpenAI 兼容服务器
        # 例如：使用 ollama、vllm 或 lm-studio
        local_server_url = "http://localhost:11434/v1"  # Ollama 默认地址

        try:
            import requests
            response = requests.get(f"{local_server_url.replace('/v1', '')}/api/tags", timeout=2)
            if response.status_code == 200:
                logger.info(f"检测到本地 Ollama 服务器")
                interpreter.llm.model = f"openai/{llm_cfg.local.model_name}"
                interpreter.llm.api_base = local_server_url
                interpreter.llm.api_key = "dummy"  # Ollama 不需要 API key
                self._use_local = True
                return
        except Exception:
            logger.info("未检测到本地 Ollama 服务器")

        # 如果没有本地服务器，回退到在线模式
        logger.warning("本地模型服务器不可用，回退到在线模式")
        interpreter.llm.model = f"openai/{llm_cfg.model}"
        interpreter.llm.api_key = llm_cfg.api_key
        interpreter.llm.api_base = llm_cfg.base_url
        self._use_local = False

    def execute(self, user_command: str) -> dict:
        """
        使用 Open Interpreter 执行用户命令

        Args:
            user_command: 用户的自然语言命令

        Returns:
            {
                "success": bool,
                "response": str,
                "messages": list  # Open Interpreter 的完整消息历史
            }
        """
        try:
            interpreter = self._get_interpreter()

            # 执行命令
            messages = interpreter.chat(user_command)

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
        """
        从 Open Interpreter 消息中提取用户友好的响应

        Open Interpreter 返回的消息格式：
        [
            {"role": "assistant", "type": "code", "format": "python", "content": "..."},
            {"role": "computer", "type": "console", "format": "output", "content": "..."},
            {"role": "assistant", "type": "message", "content": "任务完成"}
        ]
        """
        if not messages:
            return "任务完成"

        # 提取最后的 assistant message
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("type") == "message":
                content = msg.get("content", "").strip()
                if content:
                    return content

        # 如果没有 message 类型的响应，检查是否有执行结果
        output_parts = []
        for msg in messages:
            if msg.get("role") == "computer" and msg.get("type") == "console":
                content = msg.get("content", "").strip()
                if content and not content.startswith("Error"):
                    output_parts.append(content)

        if output_parts:
            return "\n".join(output_parts)

        return "任务完成"

    def reset(self):
        """重置 interpreter 状态（开始新的对话）"""
        if self._interpreter:
            self._interpreter.messages = []


# 全局实例（可选）
_executor: Optional[InterpreterExecutor] = None


def get_executor(auto_run: bool = True, verbose: bool = False) -> InterpreterExecutor:
    """获取或创建 InterpreterExecutor 单例"""
    global _executor
    if _executor is None:
        _executor = InterpreterExecutor(auto_run=auto_run, verbose=verbose)
    return _executor