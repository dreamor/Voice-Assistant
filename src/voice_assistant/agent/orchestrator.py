"""
AgentOrchestrator - Agent 循环控制器
LLM function calling → tool 执行 → 结果回传 → 循环
"""
import json
import logging
import time
from collections.abc import Callable, Generator

from voice_assistant.agent.events import AgentEvent, AgentResult, EventType, new_call_id
from voice_assistant.agent.llm_client import (
    call_llm_with_tools,
    call_llm_with_tools_stream,
)
from voice_assistant.security.safe_guard import GuardResult
from voice_assistant.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5


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

    def _build_tool_result_event(
        self,
        tool_name: str,
        tool_call_id: str,
        exec_result: dict,
        duration_ms: int,
    ) -> AgentEvent:
        """从执行结果构建 TOOL_EXECUTION_END 事件"""
        tool_content = exec_result.get("result", "")
        tool_success = exec_result.get("success", False)
        tool_data = exec_result.get("data", {})
        display_hint = exec_result.get("display_hint", "text")

        if not tool_success:
            tool_content = f"错误: {tool_content}"
            display_hint = "error"

        return AgentEvent(
            type=EventType.TOOL_EXECUTION_END,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_result=tool_content,
            tool_result_data=tool_data if tool_data else None,
            tool_display_hint=display_hint,
            tool_success=tool_success,
            duration_ms=duration_ms,
        )

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

        生成 AgentEvent 事件（v2 结构化事件类型）：
        - AGENT_START / AGENT_END: Agent 循环开始/结束
        - TURN_START / TURN_END: 每轮 LLM 调用
        - MESSAGE_DELTA: LLM 文本增量
        - TOOL_CALL: LLM 决定调用工具（含参数和 call_id）
        - TOOL_EXECUTION_START / TOOL_EXECUTION_END: 工具执行开始/结束
        - ERROR: 发生错误
        """
        messages = self._prepare_messages(conversation_history, user_text)
        tool_calls_made: list[str] = []
        confirmations_needed: list[GuardResult] = []
        iteration = 0
        tools = self._registry.get_openai_tools()

        yield AgentEvent(type=EventType.AGENT_START)
        self._emit_event("agent_start", {"user_text": user_text, "max_iterations": self._max_iterations})

        while iteration < self._max_iterations:
            iteration += 1
            logger.info(f"[AgentOrchestrator] stream iteration {iteration}/{self._max_iterations}")
            yield AgentEvent(type=EventType.TURN_START, iteration=iteration)

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
                    yield AgentEvent(type=EventType.MESSAGE_DELTA, content=event.content)

                elif event.type == "tool_calls" and event.tool_calls:
                    tool_calls_from_stream = event.tool_calls
                    finish_reason = event.finish_reason

                elif event.type == "error":
                    had_error = True
                    yield AgentEvent(type=EventType.ERROR, content=event.content)
                    self._emit_event("agent_end", {"success": False, "iterations": iteration, "error": event.content})
                    yield AgentEvent(
                        type=EventType.AGENT_END,
                        result=AgentResult(
                            success=False,
                            response=event.content or "处理失败",
                            tool_calls_made=tool_calls_made,
                            iterations=iteration,
                        ),
                    )
                    return

                elif event.type == "done":
                    finish_reason = event.finish_reason or finish_reason

            if had_error:
                return

            # LLM 返回纯文本
            if finish_reason == "stop" and accumulated_content:
                messages.append({"role": "assistant", "content": accumulated_content})
                yield AgentEvent(type=EventType.TURN_END, iteration=iteration)
                final = self._build_final_result(accumulated_content, tool_calls_made, confirmations_needed, iteration)
                self._emit_event("agent_end", {"success": True, "iterations": iteration, "tool_calls": tool_calls_made})
                yield AgentEvent(type=EventType.AGENT_END, result=final)
                return

            # Tool calls
            if not tool_calls_from_stream:
                logger.info("[AgentOrchestrator] stream: 无 tool call，结束")
                response_text = accumulated_content or "任务完成"
                if accumulated_content:
                    messages.append({"role": "assistant", "content": accumulated_content})
                yield AgentEvent(type=EventType.TURN_END, iteration=iteration)
                final = self._build_final_result(response_text, tool_calls_made, confirmations_needed, iteration)
                self._emit_event("agent_end", {"success": True, "iterations": iteration, "tool_calls": tool_calls_made})
                yield AgentEvent(type=EventType.AGENT_END, result=final)
                return

            # 发出 TOOL_CALL 事件（LLM 决定调用哪些工具）
            for tc in tool_calls_from_stream:
                call_id = tc.get("id", new_call_id())
                yield AgentEvent(
                    type=EventType.TOOL_CALL,
                    tool_name=tc["name"],
                    tool_arguments=tc.get("arguments", {}),
                    tool_call_id=call_id,
                    iteration=iteration,
                )

            # 执行每个工具调用
            for tc in tool_calls_from_stream:
                tool_name = tc["name"]
                arguments = tc.get("arguments", {})
                call_id = tc.get("id", new_call_id())
                logger.info(f"[AgentOrchestrator] stream Tool call: {tool_name}({arguments})")

                yield AgentEvent(
                    type=EventType.TOOL_EXECUTION_START,
                    tool_name=tool_name,
                    tool_arguments=arguments,
                    tool_call_id=call_id,
                    iteration=iteration,
                )

                start_time = time.monotonic()

                # 执行工具（含确认流程）
                exec_result_data = self._registry.execute(tool_name, arguments)
                result = None
                if exec_result_data.get("needs_confirmation"):
                    guard = exec_result_data.get("guard_result")
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
                        result = AgentResult(
                            success=True,
                            response=f"{guard.message}\n请在页面上确认此操作。",
                            tool_calls_made=tool_calls_made,
                            confirmations_needed=confirmations_needed,
                        )
                    else:
                        exec_result_data = self._registry.execute_confirmed(tool_name, arguments)

                duration_ms = int((time.monotonic() - start_time) * 1000)

                if result is not None:
                    result.iterations = iteration
                    self._emit_event("agent_end", {"success": True, "iterations": iteration, "tool_calls": tool_calls_made, "confirmation_needed": True})
                    yield AgentEvent(
                        type=EventType.AGENT_END,
                        result=result,
                    )
                    return

                tool_calls_made.append(tool_name)
                tool_content = exec_result_data.get("result", "")
                if not exec_result_data.get("success"):
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

                tool_success = exec_result_data.get("success", False)
                tool_data = exec_result_data.get("data")
                tool_hint = exec_result_data.get("display_hint", "text")
                if not tool_success:
                    tool_hint = "error"

                yield AgentEvent(
                    type=EventType.TOOL_EXECUTION_END,
                    tool_name=tool_name,
                    tool_call_id=call_id,
                    tool_result=tool_content,
                    tool_result_data=tool_data if tool_data else None,
                    tool_display_hint=tool_hint,
                    tool_success=tool_success,
                    duration_ms=duration_ms,
                    iteration=iteration,
                )

            yield AgentEvent(type=EventType.TURN_END, iteration=iteration)

        # 达到最大迭代次数
        result = self._build_final_result(
            "任务部分完成，部分操作可能需要额外步骤。",
            tool_calls_made, confirmations_needed, iteration,
        )
        self._emit_event("agent_end", {"success": result.success, "iterations": iteration, "tool_calls": tool_calls_made})
        yield AgentEvent(type=EventType.AGENT_END, result=result)

    @staticmethod
    def _emit_event(name: str, data: dict) -> None:
        """通过 EventBus 发送全局事件（通知用途，不可拦截）"""
        try:
            from voice_assistant.core.events import Event, EventName, get_event_bus
            bus = get_event_bus()
            event_name = EventName(name) if name in EventName.__members__ else name
            bus.emit(Event(name=event_name, data=data))
        except Exception:
            pass
