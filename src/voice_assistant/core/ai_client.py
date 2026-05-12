"""
AI Client 模块
使用 litellm 统一调用在线 LLM API
支持模型自动切换和故障转移
"""
import logging
import re

import litellm

from voice_assistant.config import config
from voice_assistant.core.model_manager import model_manager
from voice_assistant.security.validation import (
    InputValidationError,
    RateLimitError,
    llm_limiter,
    validate_text_input,
)

logger = logging.getLogger(__name__)

# litellm 配置：自动丢弃不支持的参数
litellm.drop_params = True

# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = "你是一个友好的中文语音助手，回复要简洁口语化，适合语音播放。"

# 模型队列是否已初始化
_model_queue_initialized = False


def _ensure_model_queue():
    """确保模型队列已初始化"""
    global _model_queue_initialized
    if not _model_queue_initialized:
        model_manager.build_model_queue()
        _model_queue_initialized = True


def ask_ai_stream(text, conversation_history=None):
    """使用流式 API 获取 AI 回复

    Args:
        text: 用户输入文本
        conversation_history: 对话历史

    Returns:
        生成器，产生 AI 回复

    Raises:
        InputValidationError: 输入验证失败
        RateLimitError: 超过速率限制
    """
    yield from ask_online_ai_stream(text, conversation_history)


def ask_online_ai_stream(text, conversation_history=None):
    """使用 litellm 流式 API 获取 AI 回复，支持模型自动切换

    Args:
        text: 用户输入文本
        conversation_history: 对话历史

    Returns:
        生成器，产生 AI 回复

    Raises:
        InputValidationError: 输入验证失败
        RateLimitError: 超过速率限制
    """
    global _model_queue_initialized

    if conversation_history is None:
        conversation_history = []

    try:
        cleaned_text = validate_text_input(text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    except InputValidationError as e:
        yield f"抱歉，输入验证失败：{e}"
        return

    try:
        llm_limiter.check()
    except RateLimitError as e:
        yield f"抱歉，{e}"
        return

    # 确保模型队列已初始化
    _ensure_model_queue()

    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
    ]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": cleaned_text})

    # 尝试使用当前模型，失败时自动切换
    queue = model_manager.get_queue()
    max_attempts = len(queue.models) if queue else 1

    for attempt in range(max_attempts):
        current_model = model_manager.get_current_model()
        if current_model is None:
            yield "抱歉，没有可用的模型。"
            return

        try:
            print(f"  [AI] Thinking... (模型: {current_model.name})")

            response = litellm.completion(
                model=current_model.litellm_model,
                messages=messages,
                api_key=current_model.api_key,
                api_base=current_model.base_url if current_model.base_url else None,
                max_tokens=config.llm.max_tokens,
                temperature=config.llm.temperature,
                stream=True,
                timeout=120,
            )

            # 成功获取响应，解析流式数据
            full_content = []
            stream_failed = False

            try:
                for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    content = delta.content or ""
                    if content:
                        full_content.append(content)
                        yield ''.join(full_content)

            except Exception as stream_error:
                stream_failed = True
                if model_manager.should_switch_model(stream_error) and model_manager.get_queue().has_fallback():
                    logger.warning(f"[AI] 流式响应失败: {stream_error}，切换备用模型")
                    model_manager.switch_to_next_model()
                    continue

            if not stream_failed:
                final_content = ''.join(full_content)

                if final_content:
                    conversation_history.append({"role": "user", "content": cleaned_text})
                    conversation_history.append({"role": "assistant", "content": final_content})

                    max_turns = config.history.max_turns
                    if len(conversation_history) > max_turns:
                        conversation_history[:] = conversation_history[-max_turns:]

                    # 成功后重置到主模型
                    model_manager.reset_to_primary()
                    return
                else:
                    # 空响应，尝试切换备用模型
                    logger.warning(f"[AI] 模型 {current_model.name} 返回空响应，尝试备用模型")
                    if model_manager.get_queue().has_fallback():
                        model_manager.switch_to_next_model()
                        continue
                    yield "抱歉，没有得到有效回复。"
                    return

        except litellm.Timeout:
            if model_manager.get_queue().has_fallback():
                logger.warning("[AI] 请求超时，切换备用模型")
                model_manager.switch_to_next_model()
                continue
            yield "抱歉，AI 响应超时了。"
            return

        except litellm.APIConnectionError:
            if model_manager.get_queue().has_fallback():
                logger.warning("[AI] 连接失败，切换备用模型")
                model_manager.switch_to_next_model()
                continue
            yield "抱歉，网络连接失败。"
            return

        except litellm.APIError as e:
            error_msg = str(e)
            if model_manager.should_switch_model(e) and model_manager.get_queue().has_fallback():
                logger.warning(f"[AI] 模型 {current_model.name} 失败: {error_msg}，切换备用模型")
                model_manager.switch_to_next_model()
                continue
            yield f"抱歉，AI 服务暂时不可用 ({error_msg})。"
            return

        except Exception as e:
            if model_manager.should_switch_model(e) and model_manager.get_queue().has_fallback():
                logger.warning(f"[AI] 请求异常: {e}，切换备用模型")
                model_manager.switch_to_next_model()
                continue
            yield "抱歉，发生错误。"
            return

    yield "抱歉，所有模型均不可用，请稍后重试。"


def get_current_model_name() -> str:
    """获取当前使用的模型名称"""
    _ensure_model_queue()
    model = model_manager.get_current_model()
    return model.name if model else "未配置"


def list_available_models() -> list[str]:
    """获取所有可用模型列表（从配置文件读取）"""
    from voice_assistant.config import config
    return config.llm_models.get_model_names()


def get_model_queue_info() -> dict:
    """获取模型队列信息"""
    _ensure_model_queue()
    queue = model_manager.get_queue()
    if queue is None:
        return {"models": [], "current_index": 0}

    return {
        "models": [m.name for m in queue.models],
        "current_index": queue.current_index,
        "current_model": queue.current().name if queue.current() else None,
    }