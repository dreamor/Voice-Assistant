"""
本地 LLM 模块
使用 LiteRT-LM 进行本地推理
"""
import logging
import os
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# LiteRT-LM 可选依赖
try:
    import litert_lm
    LITERT_LM_AVAILABLE = True
except ImportError:
    LITERT_LM_AVAILABLE = False
    logger.warning("LiteRT-LM 未安装，本地模型功能不可用。请运行: pip install litert-lm-api-nightly")


class LocalLLMError(Exception):
    """本地 LLM 错误"""
    pass


class LocalLLMEngine:
    """本地 LLM 引擎，使用 LiteRT-LM"""

    def __init__(self, model_path: str, system_prompt: Optional[str] = None):
        """初始化本地 LLM 引擎

        Args:
            model_path: LiteRT-LM 模型文件路径 (.litertlm)
            system_prompt: 系统提示词

        Raises:
            LocalLLMError: 初始化失败
        """
        if not LITERT_LM_AVAILABLE:
            raise LocalLLMError("LiteRT-LM 未安装")

        self.model_path = model_path
        self.system_prompt = system_prompt or "你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。"
        self._engine = None
        self._conversation = None

        # 验证模型文件
        if not os.path.exists(model_path):
            raise LocalLLMError(f"模型文件不存在: {model_path}")

        self._init_engine()

    def _init_engine(self):
        """初始化 LiteRT-LM 引擎"""
        try:
            # 设置日志级别
            litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)

            # 初始化引擎
            self._engine = litert_lm.Engine(self.model_path)
            logger.info(f"本地 LLM 引擎初始化成功: {self.model_path}")

        except Exception as e:
            raise LocalLLMError(f"引擎初始化失败: {e}")

    def create_conversation(self) -> None:
        """创建新对话"""
        if self._engine is None:
            raise LocalLLMError("引擎未初始化")

        messages = [
            {"role": "system", "content": [{"type": "text", "text": self.system_prompt}]}
        ]

        self._conversation = self._engine.create_conversation(messages=messages)
        logger.debug("新对话已创建")

    def send_message(self, text: str) -> str:
        """发送消息并获取完整回复

        Args:
            text: 用户输入

        Returns:
            模型回复
        """
        if self._conversation is None:
            self.create_conversation()

        try:
            response = self._conversation.send_message(text)
            return response["content"][0]["text"]
        except Exception as e:
            logger.error(f"本地 LLM 推理错误: {e}")
            raise LocalLLMError(f"推理失败: {e}")

    def send_message_stream(self, text: str) -> Generator[str, None, None]:
        """发送消息并流式获取回复

        Args:
            text: 用户输入

        Yields:
            回复文本片段
        """
        if self._conversation is None:
            self.create_conversation()

        try:
            for chunk in self._conversation.send_message_async(text):
                for item in chunk.get("content", []):
                    if item.get("type") == "text":
                        yield item["text"]
        except Exception as e:
            logger.error(f"本地 LLM 流式推理错误: {e}")
            raise LocalLLMError(f"推理失败: {e}")

    def close(self):
        """关闭引擎，释放资源"""
        if self._conversation:
            try:
                self._conversation.__exit__(None, None, None)
            except Exception:
                pass
            self._conversation = None

        if self._engine:
            try:
                self._engine.__exit__(None, None, None)
            except Exception:
                pass
            self._engine = None

        logger.debug("本地 LLM 引擎已关闭")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class LocalLLMClient:
    """本地 LLM 客户端，提供与在线 LLM 兼容的接口"""

    def __init__(self, model_path: str, system_prompt: Optional[str] = None):
        """初始化客户端

        Args:
            model_path: 模型路径
            system_prompt: 系统提示词
        """
        self.model_path = model_path
        self.system_prompt = system_prompt
        self._engine: Optional[LocalLLMEngine] = None
        self._conversation_history: list = []

    def _ensure_engine(self):
        """确保引擎已初始化"""
        if self._engine is None:
            self._engine = LocalLLMEngine(self.model_path, self.system_prompt)
            self._engine.create_conversation()

    def ask_stream(self, text: str, conversation_history: Optional[list] = None) -> Generator[str, None, None]:
        """流式获取回复（兼容在线 LLM 接口）

        Args:
            text: 用户输入
            conversation_history: 对话历史（本地模式下忽略，由引擎管理）

        Yields:
            回复文本片段
        """
        try:
            self._ensure_engine()

            full_response = []
            for chunk in self._engine.send_message_stream(text):
                full_response.append(chunk)
                yield ''.join(full_response)

        except LocalLLMError as e:
            yield f"抱歉，本地模型推理失败：{e}"
        except Exception as e:
            yield f"抱歉，发生错误：{e}"

    def close(self):
        """关闭客户端"""
        if self._engine:
            self._engine.close()
            self._engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def download_gemma_model(output_dir: str = "models") -> str:
    """下载 Gemma-4-E2B-it LiteRT-LM 模型

    Args:
        output_dir: 输出目录

    Returns:
        模型文件路径
    """
    import subprocess

    model_dir = Path(output_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / "gemma-4-E2B-it.litertlm"

    if model_path.exists():
        logger.info(f"模型已存在: {model_path}")
        return str(model_path)

    logger.info("正在下载 Gemma-4-E2B-it LiteRT-LM 模型...")

    # 使用 litert-lm CLI 下载
    cmd = [
        "litert-lm", "run",
        "--from-huggingface-repo=litert-community/gemma-4-E2B-it-litert-lm",
        "gemma-4-E2B-it.litertlm",
        "--prompt=test",
        f"--output={output_dir}"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            logger.info(f"模型下载完成: {model_path}")
            return str(model_path)
        else:
            logger.error(f"模型下载失败: {result.stderr}")
            raise LocalLLMError(f"模型下载失败: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise LocalLLMError("模型下载超时")
    except FileNotFoundError:
        raise LocalLLMError("litert-lm CLI 未安装，请运行: pip install litert-lm")


if __name__ == "__main__":
    # 测试代码
    print("本地 LLM 模块测试:")

    if not LITERT_LM_AVAILABLE:
        print("  LiteRT-LM 未安装，请运行:")
        print("  pip install litert-lm-api-nightly")
    else:
        print("  LiteRT-LM 已安装")

        # 测试模型路径
        model_path = "models/gemma-4-E2B-it.litertlm"
        if os.path.exists(model_path):
            print(f"  模型文件存在: {model_path}")

            try:
                with LocalLLMClient(model_path) as client:
                    print("  发送测试消息...")
                    for chunk in client.ask_stream("你好"):
                        print(f"  回复: {chunk}")
            except Exception as e:
                print(f"  测试失败: {e}")
        else:
            print(f"  模型文件不存在: {model_path}")
            print("  请先下载模型:")
            print("  litert-lm run --from-huggingface-repo=litert-community/gemma-4-E2B-it-litert-lm gemma-4-E2B-it.litertlm --prompt=test --output=models")