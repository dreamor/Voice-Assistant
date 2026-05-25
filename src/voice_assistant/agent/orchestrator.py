"""
AgentOrchestrator - Agent 循环控制器
LLM function calling → tool 执行 → 结果回传 → 循环
"""
import json
import logging
from collections.abc import Callable, Generator
from dataclasses import dataclass, field

from voice_assistant.agent.llm_client import (
    call_llm_with_tools,
    call_llm_with_tools_stream,
)
from voice_assistant.security.safe_guard import GuardResult
from voice_assistant.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5


@dataclass
class AgentResult:
    success: bool
    response: str
    tool_calls_made: list[str] = field(default_factory=list)
    confirmations_needed: list[GuardResult] = field(default_factory=list)
    iterations: int = 0
    fallback_used: bool = False


@dataclass
class AgentEvent:
    """Agent 循环流式事件"""
    type: str  # "llm_token" | "tool_start" | "tool_result" | "complete" | "error"
    content: str | None = None
    tool_name: str | None = None
    tool_arguments: dict | None = None
    tool_result: str | None = None
    success: bool | None = None
    result: AgentResult | None = None


class AgentOrchestrator:
    """Agent 循环控制器"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        max_iterations: int = MAX_ITERATIONS,
        confirm_callback: Callable[[str, dict, GuardResult], bool] | None = None,
    ):
        self._registry = tool_registry
        self._max_iterations = max_iterations
        self._confirm_callback = confirm_callback  # 异步回调: (tool_name, args, guard) -> approved

    def _prepare_messages(
        self,
        conversation_history: list | None,
        user_text: str,
    ) -> list:
        """准备消息列表，复制历史并追加用户输入。"""
        messages = list(conversation_history) if conversation_history else []
        messages.append({"role": "user", "content": user_text})
        return messages

    def _execute_tool_call(
        self,
        tc: dict,
        messages: list,
        tool_calls_made: list[str],
        confirmations_needed: list[GuardResult],
    ) -> AgentResult | None:
        """执行单个工具调用，处理确认流程。

        Args:
            tc: 工具调用字典 {"name", "arguments", "id"}
            messages: 消息列表（会被修改）
            tool_calls_made: 已执行工具名列表（会被修改）
            confirmations_needed: 需确认列表（会被修改）

        Returns:
            如果需要用户确认且未获批准，返回 AgentResult（表示应终止循环）。
            否则返回 None，表示工具已执行完成，应继续循环。
        """
        tool_name = tc["name"]
        arguments = tc.get("arguments", {})

        exec_result = self._registry.execute(tool_name, arguments)

        if exec_result.get("needs_confirmation"):
            guard = exec_result.get("guard_result")
            confirmations_needed.append(guard)

            approved = False
            if self._confirm_callback:
                approved = self._confirm_callback(tool_name, arguments, guard)

            if not approved:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "name": tool_name,
                    "content": f"操作需要用户确认: {guard.message}",
                })
                return AgentResult(
                    success=True,
                    response=f"{guard.message}\n请在页面上确认此操作。",
                    tool_calls_made=tool_calls_made,
                    confirmations_needed=confirmations_needed,
                )

            exec_result = self._registry.execute_confirmed(tool_name, arguments)

        tool_calls_made.append(tool_name)

        tool_content = exec_result.get("result", "")
        if not exec_result.get("success"):
            tool_content = f"错误: {tool_content}"

        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": tc.get("id", ""),
                "type": "function",
                "function": {"name": tool_name, "arguments": json.dumps(arguments, ensure_ascii=False)}
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": tc.get("id", ""),
            "name": tool_name,
            "content": tool_content,
        })

        return None

    def _build_final_result(
        self,
        response: str,
        tool_calls_made: list[str],
        confirmations_needed: list[GuardResult],
        iteration: int,
        success: bool = True,
    ) -> AgentResult:
        """构建最终结果。"""
        return AgentResult(
            success=success,
            response=response,
            tool_calls_made=tool_calls_made,
            confirmations_needed=confirmations_needed,
            iterations=iteration,
        )

    def run(
        self,
        user_text: str,
        conversation_history: list | None = None,
        extra_system: str = "",
    ) -> AgentResult:
        """执行 Agent 循环

        Args:
            user_text: 用户输入
            conversation_history: 对话上下文

        Returns:
            AgentResult
        """
        messages = self._prepare_messages(conversation_history, user_text)
        tool_calls_made: list[str] = []
        confirmations_needed: list[GuardResult] = []
        iteration = 0
        tools = self._registry.get_openai_tools()

        while iteration < self._max_iterations:
            iteration += 1
            logger.info(f"[AgentOrchestrator] iteration {iteration}/{self._max_iterations}")

            response = call_llm_with_tools(
                user_text=user_text if iteration == 1 else "继续",
                tools=tools,
                conversation_history=messages,
                extra_system=extra_system,
            )

            # LLM 返回纯文本
            if response["finish_reason"] == "stop" and response["content"]:
                messages.append({"role": "assistant", "content": response["content"]})
                return self._build_final_result(
                    response["content"], tool_calls_made, confirmations_needed, iteration,
                )

            # 错误
            if response["finish_reason"] == "error":
                return self._build_final_result(
                    response.get("content", "处理失败"),
                    tool_calls_made, confirmations_needed, iteration, success=False,
                )

            # Tool calls
            tool_calls = response.get("tool_calls") or []
            if not tool_calls:
                logger.info("[AgentOrchestrator] 无 tool call，结束")
                return self._build_final_result(
                    response.get("content", "任务完成"),
                    tool_calls_made, confirmations_needed, iteration,
                )

            for tc in tool_calls:
                logger.info(f"[AgentOrchestrator] Tool call: {tc['name']}({tc.get('arguments', {})})")
                result = self._execute_tool_call(tc, messages, tool_calls_made, confirmations_needed)
                if result is not None:
                    result.iterations = iteration
                    return result

        # 达到最大迭代次数
        return self._build_final_result(
            "任务部分完成，部分操作可能需要额外步骤。",
            tool_calls_made, confirmations_needed, iteration,
        )

    def run_with_confirm(
        self,
        user_text: str,
        pending_confirm: dict,
        conversation_history: list | None = None,
    ) -> AgentResult:
        """带已确认操作的继续执行

        Args:
            user_text: 原始用户输入
            pending_confirm: {"tool_name": str, "arguments": dict, "approved": bool}
            conversation_history: 上下文
        """
        history = list(conversation_history) if conversation_history else []

        if pending_confirm.get("approved"):
            tool_name = pending_confirm["tool_name"]
            arguments = pending_confirm["arguments"]
            exec_result = self._registry.execute_confirmed(tool_name, arguments)

            history.append({"role": "user", "content": user_text})
            history.append({
                "role": "tool",
                "tool_call_id": pending_confirm.get("id", ""),
                "name": tool_name,
                "content": exec_result.get("result", ""),
            })

            return self.run(
                user_text="操作已确认，请继续并汇报结果",
                conversation_history=history,
            )

        return AgentResult(
            success=True,
            response="操作已取消。",
            tool_calls_made=[],
        )

    def run_stream(
        self,
        user_text: str,
        conversation_history: list | None = None,
        extra_system: str = "",
    ) -> Generator[AgentEvent, None, None]:
        """流式执行 Agent 循环

        生成 AgentEvent 事件：
        - type="llm_token": LLM 文本增量，content 包含新增文本
        - type="tool_start": 即将执行工具，tool_name/tool_arguments
        - type="tool_result": 工具执行结果，tool_name/tool_result/success
        - type="complete": 循环结束，result 包含 AgentResult
        - type="error": 发生错误，content 包含错误信息

        Args:
            user_text: 用户输入
            conversation_history: 对话上下文
        """
        messages = self._prepare_messages(conversation_history, user_text)
        tool_calls_made: list[str] = []
        confirmations_needed: list[GuardResult] = []
        iteration = 0
        tools = self._registry.get_openai_tools()

        while iteration < self._max_iterations:
            iteration += 1
            logger.info(f"[AgentOrchestrator] stream iteration {iteration}/{self._max_iterations}")

            accumulated_content = ""
            tool_calls_from_stream: list = []
            finish_reason = None
            had_error = False

            for event in call_llm_with_tools_stream(
                user_text=user_text if iteration == 1 else "继续",
                tools=tools,
                conversation_history=messages,
                extra_system=extra_system,
            ):
                if event.type == "token" and event.content:
                    accumulated_content += event.content
                    yield AgentEvent(type="llm_token", content=event.content)

                elif event.type == "tool_calls" and event.tool_calls:
                    tool_calls_from_stream = event.tool_calls
                    finish_reason = event.finish_reason

                elif event.type == "error":
                    had_error = True
                    yield AgentEvent(type="error", content=event.content)
                    yield AgentEvent(type="complete", result=AgentResult(
                        success=False,
                        response=event.content or "处理失败",
                        tool_calls_made=tool_calls_made,
                        iterations=iteration,
                    ))
                    return

                elif event.type == "done":
                    finish_reason = event.finish_reason or finish_reason

            # 错误已在上面处理
            if had_error:
                return

            # LLM 返回纯文本
            if finish_reason == "stop" and accumulated_content:
                messages.append({"role": "assistant", "content": accumulated_content})
                yield AgentEvent(type="complete", result=self._build_final_result(
                    accumulated_content, tool_calls_made, confirmations_needed, iteration,
                ))
                return

            # Tool calls
            if not tool_calls_from_stream:
                logger.info("[AgentOrchestrator] stream: 无 tool call，结束")
                response_text = accumulated_content or "任务完成"
                if accumulated_content:
                    messages.append({"role": "assistant", "content": accumulated_content})
                yield AgentEvent(type="complete", result=self._build_final_result(
                    response_text, tool_calls_made, confirmations_needed, iteration,
                ))
                return

            for tc in tool_calls_from_stream:
                tool_name = tc["name"]
                arguments = tc.get("arguments", {})
                logger.info(f"[AgentOrchestrator] stream Tool call: {tool_name}({arguments})")

                yield AgentEvent(type="tool_start", tool_name=tool_name, tool_arguments=arguments)

                # 执行工具（含确认流程）
                result = self._execute_tool_call(tc, messages, tool_calls_made, confirmations_needed)
                if result is not None:
                    result.iterations = iteration
                    yield AgentEvent(type="complete", result=result)
                    return

                # 从 messages 中提取 _execute_tool_call 写入的工具结果
                last_tool_content = ""
                for msg in reversed(messages):
                    if msg.get("role") == "tool" and msg.get("name") == tool_name:
                        last_tool_content = msg.get("content", "")
                        break

                tool_success = not last_tool_content.startswith("错误:")
                yield AgentEvent(
                    type="tool_result",
                    tool_name=tool_name,
                    tool_result=last_tool_content,
                    success=tool_success,
                )

        # 达到最大迭代次数
        yield AgentEvent(type="complete", result=self._build_final_result(
            "任务部分完成，部分操作可能需要额外步骤。",
            tool_calls_made, confirmations_needed, iteration,
        ))
