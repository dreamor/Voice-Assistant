"""
VoiceSession - 统一的语音会话管理

ASR + Agent Loop（LLM + function calling + tool 执行）+ TTS + 历史
"""
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass

from voice_assistant.audio.asr_provider import ASRProvider, create_asr_provider
from voice_assistant.audio.tts import TTSProvider, create_tts_provider
from voice_assistant.config import config
from voice_assistant.core.asr_corrector import correct_asr_result
from voice_assistant.core.lifecycle import get_lifecycle

logger = logging.getLogger(__name__)


def _build_tool_registry():
    """根据配置构建 ToolRegistry（委托给 AppLifecycle）"""
    return get_lifecycle().build_tool_registry()


def get_mcp_manager():
    """供 Web UI / LLM tool 获取当前 MCP manager（向后兼容）"""
    return get_lifecycle().mcp_manager


def get_skill_manager():
    """供 LLM meta tool / Web UI 获取当前 SkillManager（向后兼容）"""
    return get_lifecycle().skill_manager


def _build_skill_addendum(user_text: str) -> str:
    """每次 LLM 调用前生成 system prompt 补丁"""
    return get_lifecycle().build_skill_addendum(user_text)


def _build_tool_group_hint() -> str:
    """生成工具分组提示，告知 LLM 可按需请求加载额外工具组"""
    from voice_assistant.tools.tool_groups import get_group_summary
    return get_group_summary()


def shutdown_mcp() -> None:
    """供应用退出钩子调用（向后兼容）"""
    from voice_assistant.core.lifecycle import shutdown_lifecycle
    shutdown_lifecycle()


@dataclass
class ProcessResult:
    """处理结果"""
    response: str
    intent_type: str = "agent"
    confidence: float = 1.0
    execution_output: str | None = None
    history_updated: bool = False


class VoiceSession:
    """统一的语音会话管理

    通过 Agent Loop 处理所有用户输入：function calling → tool 执行 → 循环。
    无 tool 调用时 LLM 直接生成回答（即纯对话）。
    """

    def __init__(
        self,
        max_response_length: int = 200,
        on_intent_detected: Callable[[str, float], None] | None = None,
        on_execution_start: Callable[[], None] | None = None,
        on_execution_end: Callable[[], None] | None = None,
    ):
        self._max_response_length = max_response_length

        self._on_intent_detected = on_intent_detected
        self._on_execution_start = on_execution_start
        self._on_execution_end = on_execution_end

        # 确认回调（由 Web UI 设置）
        self._confirm_callback: Callable | None = None

        # 组件（延迟初始化）
        self._asr: ASRProvider | None = None
        self._tts: TTSProvider | None = None
        self._orchestrator = None  # AgentOrchestrator
        self._history: list = []
        self._max_history_turns = max(2, getattr(config.history, "max_turns", 20))
        self._max_context_tokens = getattr(config.history, "max_context_tokens", 6000)
        self._initialized = False

    def initialize(self) -> bool:
        """初始化组件"""
        try:
            self._asr = create_asr_provider(config)
            self._tts = create_tts_provider(config)

            from voice_assistant.agent.orchestrator import AgentOrchestrator

            tool_registry = _build_tool_registry()
            self._orchestrator = AgentOrchestrator(
                tool_registry=tool_registry,
                max_iterations=config.agent.max_iterations,
            )
            logger.info("[VoiceSession] AgentOrchestrator 初始化成功")

            self._initialized = True
            logger.info("[VoiceSession] 初始化成功")
            return True

        except Exception as e:
            logger.error(f"[VoiceSession] 初始化失败: {e}")
            return False

    def _ensure_initialized(self):
        if not self._initialized:
            raise RuntimeError("VoiceSession 未初始化，请先调用 initialize()")

    def recognize(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """语音识别 + 纠错"""
        self._ensure_initialized()
        if not self._asr:
            logger.error("[VoiceSession] ASR 未初始化")
            return ""

        try:
            result = self._asr.recognize_bytes(audio_bytes, sample_rate=sample_rate)
            if not result:
                logger.warning("[VoiceSession] ASR 返回空结果")
                return ""
            corrected = correct_asr_result(result, self.get_history())
            if corrected != result:
                logger.info(f"  [Corrected] {result} → {corrected}")
            return corrected
        except Exception as e:
            logger.error(f"[VoiceSession] ASR 错误: {e}")
            return ""

    def process_text(self, user_text: str, history: list | None = None) -> ProcessResult:
        """同步处理用户文本，返回 ProcessResult"""
        self._ensure_initialized()
        if not user_text.strip():
            return ProcessResult(response="", intent_type="unknown", confidence=0.0)

        context_history = history if history is not None else list(self._history)

        if self._on_execution_start:
            self._on_execution_start()
        try:
            self._orchestrator._confirm_callback = self._confirm_callback
            extra_system = _build_skill_addendum(user_text)
            tool_group_hint = _build_tool_group_hint()
            if tool_group_hint:
                extra_system = f"{extra_system}\n\n{tool_group_hint}" if extra_system else tool_group_hint
            agent_result = self._orchestrator.run(
                user_text=user_text,
                conversation_history=context_history,
                extra_system=extra_system,
            )

            response = agent_result.response or "(无回复)"
            execution_output = (
                ", ".join(agent_result.tool_calls_made)
                if agent_result.tool_calls_made
                else None
            )

            self._append_history(user_text, response)

            return ProcessResult(
                response=response,
                intent_type="agent",
                confidence=1.0,
                execution_output=execution_output,
                history_updated=True,
            )
        except Exception as e:
            logger.error(f"[VoiceSession] Agent 循环失败: {e}", exc_info=True)
            return ProcessResult(
                response=f"抱歉，处理失败: {e}",
                intent_type="error",
                confidence=0.0,
            )
        finally:
            if self._on_execution_end:
                self._on_execution_end()

    def process_text_stream(self, user_text: str, history: list | None = None):
        """流式处理（生成 AgentEvent）"""
        from voice_assistant.agent.events import AgentEvent, EventType

        self._ensure_initialized()
        if not user_text.strip():
            yield AgentEvent(
                type=EventType.AGENT_END,
                result=ProcessResult(response="", intent_type="unknown", confidence=0.0),
            )
            return

        context_history = history if history is not None else list(self._history)

        if self._on_execution_start:
            self._on_execution_start()
        try:
            self._orchestrator._confirm_callback = self._confirm_callback
            extra_system = _build_skill_addendum(user_text)
            tool_group_hint = _build_tool_group_hint()
            if tool_group_hint:
                extra_system = f"{extra_system}\n\n{tool_group_hint}" if extra_system else tool_group_hint
            for event in self._orchestrator.run_stream(
                user_text,
                conversation_history=context_history,
                extra_system=extra_system,
            ):
                if event.type == EventType.AGENT_END and event.result:
                    response = event.result.response or "(无回复)"
                    self._append_history(user_text, response)
                    yield AgentEvent(
                        type=EventType.AGENT_END,
                        result=ProcessResult(
                            response=response,
                            intent_type="agent",
                            confidence=1.0,
                            execution_output=(
                                ", ".join(event.result.tool_calls_made)
                                if event.result.tool_calls_made
                                else None
                            ),
                            history_updated=True,
                        ),
                    )
                else:
                    yield event
        except Exception as e:
            logger.error(f"[VoiceSession] Stream Agent 循环失败: {e}", exc_info=True)
            yield AgentEvent(
                type=EventType.ERROR,
                content=f"抱歉，处理失败: {e}",
            )
        finally:
            if self._on_execution_end:
                self._on_execution_end()

    def synthesize(self, text: str) -> bytes | None:
        """语音合成"""
        if not text:
            return None

        if self._tts:
            try:
                result = self._tts.synthesize_to_bytes(text)
                if result:
                    return result
            except Exception as e:
                logger.warning(
                    f"[VoiceSession] TTS synthesize_to_bytes 失败，回退到文件模式: {e}"
                )

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            if self._tts:
                success = self._tts.synthesize(text, tmp_path)
            else:
                from voice_assistant.audio.tts import synthesize as _synthesize

                success = _synthesize(text, tmp_path)
            if success and os.path.exists(tmp_path):
                with open(tmp_path, "rb") as f:
                    return f.read()
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.debug("[VoiceSession] 临时文件清理失败（可忽略）")

    def synthesize_stream(self, text: str):
        """流式语音合成：逐句 yield 音频数据"""
        if not text or not text.strip():
            return
        self._ensure_initialized()

        if self._tts and hasattr(self._tts, "synthesize_stream"):
            try:
                yield from self._tts.synthesize_stream(text)
                return
            except Exception as e:
                logger.warning(f"[VoiceSession] 流式 TTS 失败，回退到普通模式: {e}")

        result = self.synthesize(text)
        if result:
            yield result

    def get_history(self) -> list:
        """获取对话历史副本"""
        return list(self._history)

    def set_history(self, history: list):
        """重置对话历史（用于 Web UI 加载数据库历史）"""
        self._history = list(history)
        self._trim_history()

    def clear_history(self):
        """清空对话历史"""
        self._history.clear()

    def _append_history(self, user_text: str, response: str):
        self._history.append({"role": "user", "content": user_text})
        self._history.append({"role": "assistant", "content": response})
        self._trim_history()

    def _estimate_tokens(self, messages: list) -> int:
        """粗略估算消息列表的 token 数。

        中文约 1.5 字符/token，英文约 4 字符/token。
        取较保守的估算（偏向更早裁剪）以避免超出上下文窗口。
        每条消息额外计入 4 token 的角色/格式开销。
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if content is None:
                content = ""
            # 中文按 1.5 字符/token，其余按 4 字符/token
            zh_chars = sum(1 for c in content if "一" <= c <= "鿿")
            other_chars = len(content) - zh_chars
            total += int(zh_chars / 1.5) + int(other_chars / 4) + 4
        return total

    def _trim_history(self):
        """按 token 数和轮次双重上限裁剪历史，保留系统消息。

        当 token 超限时先尝试 compaction（LLM 摘要），
        只在 compaction 后仍超限时才裁剪。
        """
        # 1. 轮次上限裁剪
        if len(self._history) > self._max_history_turns:
            self._history = self._history[-self._max_history_turns:]

        # 2. token 上限：先尝试 compaction，再裁剪
        if self._estimate_tokens(self._history) > self._max_context_tokens:
            try:
                from voice_assistant.core.compaction import compact, should_compact

                if should_compact(self._history, self._max_context_tokens):
                    result = compact(self._history, self._max_context_tokens)
                    if result.messages_removed > 0:
                        # 用压缩后的消息替换（保留系统摘要 + 最近消息）
                        self._history = [
                            m for m in self._history
                            if m.get("role") == "system"
                            and not m.get("content", "").startswith("[上下文摘要]")
                        ]
                        # 添加摘要
                        self._history.insert(0, {
                            "role": "system",
                            "content": f"[上下文摘要]\n{result.summary}",
                        })
                        # 保留最近消息
                        recent_count = result.messages_kept - 1  # 减去摘要消息
                        if recent_count > 0:
                            self._history.extend(self._history[-recent_count:])

                        logger.info(
                            f"[VoiceSession] 上下文压缩: 移除 {result.messages_removed} 条, "
                            f"{result.tokens_before} → {result.tokens_after} tokens"
                        )
            except Exception as e:
                logger.warning(f"[VoiceSession] 上下文压缩失败，降级为裁剪: {e}")

            # compaction 后仍超限，回退到简单裁剪
            if self._estimate_tokens(self._history) > self._max_context_tokens:
                system_msgs = [m for m in self._history if m.get("role") == "system"]
                non_system = [m for m in self._history if m.get("role") != "system"]

                while non_system and self._estimate_tokens(system_msgs + non_system) > self._max_context_tokens:
                    non_system.pop(0)

                self._history = system_msgs + non_system
                if non_system:
                    logger.debug(
                        f"[VoiceSession] 历史裁剪至 {len(self._history)} 条消息, "
                        f"约 {self._estimate_tokens(self._history)} tokens"
                    )

    def toggle_asr_mode(self) -> tuple[bool, str]:
        """切换本地/云端 ASR 模式"""
        try:
            if self._asr:
                self._asr.close()
            config.asr.use_local = not config.asr.use_local
            self._asr = create_asr_provider(config)
            mode = "本地" if config.asr.use_local else "云端"
            return True, mode
        except Exception as e:
            logger.error(f"[VoiceSession] ASR 模式切换失败: {e}")
            try:
                config.asr.use_local = False
                from voice_assistant.audio.cloud_asr import CloudASR

                self._asr = CloudASR(api_key=config.asr.api_key, model=config.asr.model)
            except Exception as fallback_err:
                logger.error(f"[VoiceSession] ASR 回退到云端也失败: {fallback_err}")
            return False, "云端"

    def get_asr_mode(self) -> str:
        return "本地" if config.asr.use_local else "云端"

    def cleanup(self):
        logger.info("[VoiceSession] 清理资源...")
        if self._asr:
            try:
                self._asr.close()
            except Exception as e:
                logger.warning(f"[VoiceSession] ASR 关闭异常: {e}")
        if self._tts:
            try:
                self._tts.close()
            except Exception as e:
                logger.warning(f"[VoiceSession] TTS 关闭异常: {e}")
        self._initialized = False
        logger.info("[VoiceSession] 资源清理完成")

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
