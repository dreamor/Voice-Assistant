"""
Agent LLM 客户端 - Function Calling 通信层
使用 litellm 统一调用 LLM API，支持 function calling
"""
import json
import logging
import os
import platform
from dataclasses import dataclass
from typing import Optional, Generator

import litellm

from voice_assistant.config import config
from voice_assistant.core.model_manager import model_manager
from voice_assistant.security.validation import validate_text_input, RateLimitError, llm_limiter

logger = logging.getLogger(__name__)

# litellm 配置：自动丢弃不支持的参数
litellm.drop_params = True


# ---------------------------------------------------------------------------
# 流式事件类型
# ---------------------------------------------------------------------------

@dataclass
class StreamEvent:
    """LLM 流式事件"""
    type: str  # "token" | "tool_calls" | "error" | "done"
    content: Optional[str] = None
    tool_calls: Optional[list] = None
    finish_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# 流式 tool_calls 增量组装
# ---------------------------------------------------------------------------

def _merge_tool_call_deltas(accumulated: list, delta) -> list:
    """将流式 tool_calls 片段合并到累积列表

    litellm 流式 API 每个 chunk 的 tool_calls 是增量式的：
    - 首次出现某个 index 时，包含 id、function.name（可能为空）
    - 后续 chunk 只包含 function.arguments 的追加片段
    """
    idx = getattr(delta, 'index', len(accumulated))
    while len(accumulated) <= idx:
        accumulated.append({"id": "", "name": "", "arguments": ""})

    entry = accumulated[idx]
    tc_id = getattr(delta, 'id', None)
    if tc_id:
        entry["id"] = tc_id

    func = getattr(delta, 'function', None)
    if func:
        func_name = getattr(func, 'name', None)
        if func_name:
            entry["name"] = func_name
        func_args = getattr(func, 'arguments', None)
        if func_args:
            entry["arguments"] += func_args

    return accumulated


AGENT_SYSTEM_PROMPT = f"""你是一个智能电脑助手（Jarvis），你可以通过调用函数来控制用户的电脑。

## 核心规则
1. 理解用户的意图，选择合适的函数来完成操作
2. 如果需要多个步骤，逐步执行——每一步都必须调用函数，不能只描述操作
3. **禁止仅用文字描述操作**：如果要打开文件，必须调用 open_file；如果要启动应用，必须调用 launch_application。绝不能说"正在帮你打开"而不实际调用函数
4. 执行完操作后，用简洁的中文汇报结果
5. 如果用户说的只是聊天或问问题，直接回复，不要调用函数
6. 函数调用参数要准确、具体
7. 不确定时，优先问用户确认，不要猜测

## 环境信息
- 用户主目录: {os.path.expanduser("~")}
- 桌面路径: {os.path.expanduser("~/Desktop")}
- 当前平台: {platform.system()}
- 当前工作目录: {os.getcwd()}

## 常用操作指引
- "打开XX应用" → 直接调用 launch_application(app_name="XX")
- "打开桌面上的XX文件" → 先调用 find_files 在桌面路径搜索，找到文件后立即调用 open_file(file_path=完整路径) 打开
- "搜索XXX" → web_search
- "截个屏" → take_screenshot
- "我的电脑什么配置" → get_system_info
- "打开浏览器" → launch_application(app_name="Safari" 或 "Chrome")
- "计算XXX" → calculate
- "现在有哪些程序在运行" → get_running_processes

## 重要：多步骤操作示例
用户说"打开桌面的Excel"：
1. 调用 find_files(directory="/Users/scottwang/Desktop", pattern="*.xlsx *.xls")
2. 根据搜索结果，立即调用 open_file(file_path="/Users/scottwang/Desktop/文件名.xlsx")
3. 不要在步骤之间只回复文字——必须继续调用函数
"""


def _build_messages(user_text: str, conversation_history: Optional[list] = None) -> list:
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_text})
    return messages


def call_llm_with_tools(
    user_text: str,
    tools: list[dict],
    conversation_history: Optional[list] = None,
) -> dict:
    """单次 LLM function calling 调用

    Args:
        user_text: 用户输入
        tools: OpenAI function calling tools 列表
        conversation_history: 对话历史

    Returns:
        {
            "finish_reason": "stop" | "tool_calls",
            "content": str | None,        # 纯文本回复
            "tool_calls": list[dict] | None,  # tool calls
        }
    """
    cleaned = validate_text_input(user_text)
    try:
        llm_limiter.check()
    except RateLimitError as e:
        return {"finish_reason": "error", "content": f"请求过于频繁: {e}", "tool_calls": None}

    messages = _build_messages(cleaned, conversation_history)

    # 确保模型队列已构建
    if model_manager.get_queue() is None:
        model_manager.build_model_queue()

    # 获取当前模型
    model = model_manager.get_current_model()
    if not model:
        return {"finish_reason": "error", "content": "没有可用的模型", "tool_calls": None}

    for attempt in range(len(model_manager.get_queue().models) if model_manager.get_queue() else 1):
        current = model_manager.get_current_model()
        if not current:
            break

        try:
            kwargs = {
                "model": current.litellm_model,
                "messages": messages,
                "api_key": current.api_key,
                "api_base": current.base_url if current.base_url else None,
                "max_tokens": 2048,
                "temperature": 0.1,
                "timeout": 120,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = litellm.completion(**kwargs)

            choice = response.choices[0]
            finish_reason = choice.finish_reason or "stop"
            message = choice.message

            # 成功后重置到主模型
            model_manager.reset_to_primary()

            if finish_reason == "tool_calls" or (hasattr(message, 'tool_calls') and message.tool_calls):
                raw_tool_calls = message.tool_calls
                tool_calls = []
                for tc in raw_tool_calls:
                    func = tc.function
                    try:
                        args = json.loads(func.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append({
                        "id": tc.id or "",
                        "name": func.name or "",
                        "arguments": args,
                    })
                return {
                    "finish_reason": "tool_calls",
                    "content": None,
                    "tool_calls": tool_calls,
                }

            return {
                "finish_reason": "stop",
                "content": message.content or "",
                "tool_calls": None,
            }

        except litellm.Timeout:
            if model_manager.get_queue() and model_manager.get_queue().has_fallback():
                model_manager.switch_to_next_model()
                continue
            return {"finish_reason": "error", "content": "AI 响应超时", "tool_calls": None}

        except litellm.APIConnectionError:
            if model_manager.get_queue() and model_manager.get_queue().has_fallback():
                model_manager.switch_to_next_model()
                continue
            return {"finish_reason": "error", "content": "网络连接失败", "tool_calls": None}

        except litellm.APIError as e:
            logger.warning(f"[AgentLLM] 模型 {current.name} 失败: {e}")
            if model_manager.get_queue() and model_manager.get_queue().has_fallback():
                model_manager.switch_to_next_model()
                continue
            return {"finish_reason": "error", "content": f"AI 服务不可用: {e}", "tool_calls": None}

        except Exception as e:
            logger.error(f"[AgentLLM] 请求异常: {e}")
            return {"finish_reason": "error", "content": f"AI 调用失败: {e}", "tool_calls": None}

    return {"finish_reason": "error", "content": "所有模型均不可用", "tool_calls": None}


def call_llm_with_tools_stream(
    user_text: str,
    tools: list[dict],
    conversation_history: Optional[list] = None,
) -> Generator[StreamEvent, None, None]:
    """流式 LLM function calling 调用

    生成 StreamEvent 事件：
    - type="token": 文本增量，content 包含新增文本
    - type="tool_calls": 完整的 tool_calls 已组装完毕
    - type="error": 发生错误
    - type="done": 流结束

    Args:
        user_text: 用户输入
        tools: OpenAI function calling tools 列表
        conversation_history: 对话历史
    """
    cleaned = validate_text_input(user_text)
    try:
        llm_limiter.check()
    except RateLimitError as e:
        yield StreamEvent(type="error", content=f"请求过于频繁: {e}")
        return

    messages = _build_messages(cleaned, conversation_history)

    if model_manager.get_queue() is None:
        model_manager.build_model_queue()

    model = model_manager.get_current_model()
    if not model:
        yield StreamEvent(type="error", content="没有可用的模型")
        return

    for attempt in range(len(model_manager.get_queue().models) if model_manager.get_queue() else 1):
        current = model_manager.get_current_model()
        if not current:
            break

        try:
            kwargs = {
                "model": current.litellm_model,
                "messages": messages,
                "api_key": current.api_key,
                "api_base": current.base_url if current.base_url else None,
                "max_tokens": 2048,
                "temperature": 0.1,
                "stream": True,
                "timeout": 120,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = litellm.completion(**kwargs)

            # 解析流式响应
            tool_calls_accumulated: list = []
            finish_reason = None

            for chunk in response:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason or finish_reason

                # 文本内容增量
                content_delta = delta.content or ""
                if content_delta:
                    yield StreamEvent(type="token", content=content_delta)

                # tool_calls 增量
                tc_deltas = getattr(delta, 'tool_calls', None)
                if tc_deltas:
                    for tc_delta in tc_deltas:
                        _merge_tool_call_deltas(tool_calls_accumulated, tc_delta)

            # 流结束，处理结果
            model_manager.reset_to_primary()

            if tool_calls_accumulated:
                # 组装最终 tool_calls
                parsed_calls = []
                for tc in tool_calls_accumulated:
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    parsed_calls.append({
                        "id": tc["id"],
                        "name": tc["name"],
                        "arguments": args,
                    })
                yield StreamEvent(
                    type="tool_calls",
                    tool_calls=parsed_calls,
                    finish_reason="tool_calls",
                )
            elif finish_reason == "stop":
                pass  # token 事件已经逐个 yield

            yield StreamEvent(type="done", finish_reason=finish_reason or "stop")
            return

        except litellm.Timeout:
            if model_manager.get_queue() and model_manager.get_queue().has_fallback():
                model_manager.switch_to_next_model()
                continue
            yield StreamEvent(type="error", content="AI 响应超时")
            return

        except litellm.APIConnectionError:
            if model_manager.get_queue() and model_manager.get_queue().has_fallback():
                model_manager.switch_to_next_model()
                continue
            yield StreamEvent(type="error", content="网络连接失败")
            return

        except litellm.APIError as e:
            logger.warning(f"[AgentLLM] 流式请求模型 {current.name} 失败: {e}")
            if model_manager.get_queue() and model_manager.get_queue().has_fallback():
                model_manager.switch_to_next_model()
                continue
            yield StreamEvent(type="error", content=f"AI 服务不可用: {e}")
            return

        except Exception as e:
            logger.error(f"[AgentLLM] 流式请求异常: {e}")
            if model_manager.get_queue() and model_manager.get_queue().has_fallback():
                model_manager.switch_to_next_model()
                continue
            yield StreamEvent(type="error", content=f"AI 调用失败: {e}")
            return

    yield StreamEvent(type="error", content="所有模型均不可用")