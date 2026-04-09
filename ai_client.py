"""
AI Client 模块
使用 LLM API 或本地模型进行 AI 对话
支持在线/本地模型切换
"""
import json
import logging
import re
import requests
from config import config
from security_utils import validate_text_input, llm_limiter, RateLimitError, InputValidationError

logger = logging.getLogger(__name__)

# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = "你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。"

# 本地 LLM 客户端（延迟初始化）
_local_llm_client = None


def get_local_llm_client():
    """获取本地 LLM 客户端（单例）"""
    global _local_llm_client

    if _local_llm_client is None:
        try:
            from local_llm import LocalLLMClient, LITERT_LM_AVAILABLE

            if not LITERT_LM_AVAILABLE:
                logger.warning("LiteRT-LM 未安装，本地模型不可用")
                return None

            llm_cfg = config.llm
            _local_llm_client = LocalLLMClient(
                model_path=llm_cfg.local.model_path,
                system_prompt=llm_cfg.local.system_prompt
            )
            logger.info(f"本地 LLM 客户端已初始化: {llm_cfg.local.model_path}")

        except Exception as e:
            logger.error(f"本地 LLM 客户端初始化失败: {e}")
            return None

    return _local_llm_client


def close_local_llm_client():
    """关闭本地 LLM 客户端"""
    global _local_llm_client
    if _local_llm_client:
        _local_llm_client.close()
        _local_llm_client = None


def ask_ai_stream(text, conversation_history=None):
    """使用流式API获取AI回复（自动选择本地或在线）

    Args:
        text: 用户输入文本
        conversation_history: 对话历史

    Returns:
        生成器，产生AI回复

    Raises:
        InputValidationError: 输入验证失败
        RateLimitError: 超过速率限制
    """
    # 检查是否有本地客户端（表示本地模式已激活）
    client = get_local_llm_client()

    # 根据本地客户端状态选择模式
    if client is not None:
        yield from ask_local_ai_stream(text, conversation_history)
    else:
        yield from ask_online_ai_stream(text, conversation_history)


def ask_local_ai_stream(text, conversation_history=None):
    """使用本地模型获取AI回复

    Args:
        text: 用户输入文本
        conversation_history: 对话历史（本地模式下由引擎管理）

    Returns:
        生成器，产生AI回复
    """
    # 输入验证
    try:
        cleaned_text = validate_text_input(text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    except InputValidationError as e:
        yield f"抱歉，输入验证失败：{e}"
        return

    # 获取本地客户端
    client = get_local_llm_client()
    if client is None:
        yield "抱歉，本地模型不可用。请检查 LiteRT-LM 是否正确安装。"
        return

    print("  [AI] Thinking (Local)...")

    try:
        for chunk in client.ask_stream(cleaned_text):
            yield chunk

    except Exception as e:
        logger.error(f"本地 LLM 错误: {e}")
        yield f"抱歉，本地模型推理失败：{e}"


def ask_online_ai_stream(text, conversation_history=None):
    """使用在线API获取AI回复

    Args:
        text: 用户输入文本
        conversation_history: 对话历史

    Returns:
        生成器，产生AI回复

    Raises:
        InputValidationError: 输入验证失败
        RateLimitError: 超过速率限制
    """
    if conversation_history is None:
        conversation_history = []

    # 输入验证
    try:
        cleaned_text = validate_text_input(text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    except InputValidationError as e:
        yield f"抱歉，输入验证失败：{e}"
        return

    # 速率限制检查
    try:
        llm_limiter.check()
    except RateLimitError as e:
        yield f"抱歉，{e}"
        return

    llm_cfg = config.llm

    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
    ]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": cleaned_text})

    try:
        print("  [AI] Thinking...")

        response = requests.post(
            f"{llm_cfg.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {llm_cfg.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": llm_cfg.model,
                "messages": messages,
                "max_tokens": llm_cfg.max_tokens,
                "temperature": llm_cfg.temperature,
                "stream": True,
            },
            stream=True,
            timeout=120
        )

        if response.status_code != 200:
            yield f"抱歉，AI服务暂时不可用 ({response.status_code})。"
            return

        full_content = []

        for line in response.iter_lines():
            if not line:
                continue

            line = line.decode('utf-8', errors='replace')
            if not line.startswith('data: '):
                continue

            data_str = line[6:]
            if data_str == '[DONE]':
                break

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            delta = data.get('choices', [{}])[0].get('delta', {})
            content = delta.get('content', '') or delta.get('reasoning', '')

            if content:
                full_content.append(content)
                yield ''.join(full_content)

        final_content = ''.join(full_content)

        if final_content:
            conversation_history.append({"role": "user", "content": cleaned_text})
            conversation_history.append({"role": "assistant", "content": final_content})

            max_turns = config.history.max_turns
            if len(conversation_history) > max_turns:
                conversation_history[:] = conversation_history[-max_turns:]
        else:
            yield "抱歉，没有得到有效回复。"

    except requests.Timeout:
        yield "抱歉，AI响应超时了。"
    except requests.ConnectionError:
        yield "抱歉，网络连接失败。"
    except Exception:
        yield "抱歉，发生错误。"