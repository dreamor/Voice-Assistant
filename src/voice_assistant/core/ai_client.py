"""
AI Client 模块
使用在线 LLM API 进行 AI 对话
支持模型自动切换和故障转移
"""
import json
import logging
import re

import requests

from voice_assistant.config import config
from voice_assistant.core.model_manager import model_manager, ModelConfig
from voice_assistant.security.validation import (
    InputValidationError,
    RateLimitError,
    llm_limiter,
    validate_text_input,
)

logger = logging.getLogger(__name__)

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


def _make_stream_request(model: ModelConfig, messages: list) -> requests.Response:
    """发起流式请求

    Args:
        model: 模型配置
        messages: 消息列表

    Returns:
        响应对象
    """
    return requests.post(
        f"{model.base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {model.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model.name,
            "messages": messages,
            "max_tokens": config.llm.max_tokens,
            "temperature": config.llm.temperature,
            "stream": True,
        },
        stream=True,
        timeout=120
    )


def _parse_stream_response(response: requests.Response) -> tuple[str, bool]:
    """解析流式响应

    Args:
        response: 响应对象

    Returns:
        (内容, 是否成功)
    """
    full_content = []

    for line in response.iter_lines():
        if not line:
            continue

        line = line.decode('utf-8', errors='replace')

        if line.startswith('data:'):
            data_str = line[5:].strip()
        elif line.startswith(' '):
            data_str = line[6:].strip()
        else:
            continue

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

    return ''.join(full_content), bool(full_content)


def ask_online_ai_stream(text, conversation_history=None):
    """使用在线 API 获取 AI 回复，支持模型自动切换

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
    max_attempts = 3  # 最多尝试 3 个模型
    attempt = 0

    while attempt < max_attempts:
        current_model = model_manager.get_current_model()
        if current_model is None:
            yield "抱歉，没有可用的模型。"
            return

        attempt += 1

        try:
            print(f"  [AI] Thinking... (模型: {current_model.name})")

            response = _make_stream_request(current_model, messages)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg = f"{error_msg}: {error_detail.get('error', {}).get('message', '')}"
                except Exception:
                    pass

                # 判断是否应该切换模型
                error = requests.HTTPError(error_msg)
                error.response = response
                if model_manager.should_switch_model(error) and model_manager.get_queue().has_fallback():
                    logger.warning(f"[AI] 模型 {current_model.name} 失败: {error_msg}，切换备用模型")
                    model_manager.switch_to_next_model()
                    continue
                else:
                    yield f"抱歉，AI 服务暂时不可用 ({error_msg})。"
                    return

            # 成功获取响应，解析流式数据
            full_content = []
            stream_failed = False

            try:
                for line in response.iter_lines():
                    if not line:
                        continue

                    line = line.decode('utf-8', errors='replace')

                    if line.startswith(''):
                        data_str = line[5:].strip()
                    elif line.startswith(' '):
                        data_str = line[6:].strip()
                    else:
                        continue

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
                    yield "抱歉，没有得到有效回复。"
                    return

        except requests.Timeout:
            if model_manager.get_queue().has_fallback():
                logger.warning("[AI] 请求超时，切换备用模型")
                model_manager.switch_to_next_model()
                continue
            yield "抱歉，AI 响应超时了。"
            return

        except requests.ConnectionError:
            if model_manager.get_queue().has_fallback():
                logger.warning("[AI] 连接失败，切换备用模型")
                model_manager.switch_to_next_model()
                continue
            yield "抱歉，网络连接失败。"
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


def list_available_models() -> list[dict]:
    """获取所有可用模型列表"""
    return model_manager.list_available_models()


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