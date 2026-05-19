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

logger = logging.getLogger(__name__)


_mcp_manager = None  # 全局 MCPManager 单例，由首个 registry 触发懒加载
_skill_manager = None  # 全局 SkillManager 单例


def _build_tool_registry():
    """根据配置构建 ToolRegistry（延迟导入避免循环依赖）"""
    from voice_assistant.platform import detect_platform
    from voice_assistant.security.safe_guard import SafeGuard, SecurityLevel, ToolPolicy
    from voice_assistant.tools.platform_specific import get_platform_tools
    from voice_assistant.tools.registry import ToolRegistry
    from voice_assistant.tools.universal import get_universal_tools

    guard = SafeGuard(
        policies=[
            ToolPolicy(tool_name=name, blocked=True)
            for name in config.tools.blocked
        ]
        + [
            ToolPolicy(
                tool_name=ov.name,
                override_level=SecurityLevel(ov.level),
            )
            for ov in config.tools.overrides
        ]
    )
    platform = detect_platform()
    registry = ToolRegistry(current_platform=platform, safe_guard=guard)
    registry.register_all(get_universal_tools())
    registry.register_all(get_platform_tools(platform))

    # 在 MCP server 启动前先注册 meta tools，确保「list_mcp_servers」始终可用
    from voice_assistant.tools.mcp import get_mcp_meta_tools
    registry.register_all(get_mcp_meta_tools())

    _start_mcp(registry)

    # Skill 系统：注册 meta tools + 加载磁盘上的 skill 定义
    from voice_assistant.skills.meta_tools import get_skill_meta_tools
    registry.register_all(get_skill_meta_tools())
    _start_skills()

    logger.info(
        f"[VoiceSession] 注册 {len(registry.list_tools())} 个工具 (platform={platform})"
    )
    return registry


def _start_mcp(registry) -> None:
    """启动 MCP server 并把工具桥接到 registry。失败不影响主流程。"""
    global _mcp_manager
    if _mcp_manager is not None:
        return
    try:
        from pathlib import Path

        from voice_assistant.tools.mcp import MCPManager, load_servers

        cfg_dir = Path("config")
        servers = load_servers(
            cfg_dir / "mcp_servers.yaml",
            secrets_path=cfg_dir / "secrets.yaml",
        )
        if not servers:
            return
        mgr = MCPManager(registry)
        mgr.start(servers)
        _mcp_manager = mgr
    except Exception:
        logger.exception("[VoiceSession] MCP 启动失败，已忽略")


def get_mcp_manager():
    """供 Web UI / LLM tool 获取当前 MCP manager"""
    return _mcp_manager


def _start_skills() -> None:
    """加载 skills/ 目录下的 SKILL.md。失败不影响主流程。"""
    global _skill_manager
    if _skill_manager is not None:
        return
    try:
        from pathlib import Path

        from voice_assistant.skills import SkillManager

        root = Path("skills")
        mgr = SkillManager(root)
        mgr.reload()
        _skill_manager = mgr
    except Exception:
        logger.exception("[VoiceSession] Skill 加载失败，已忽略")


def get_skill_manager():
    """供 LLM meta tool / Web UI 获取当前 SkillManager"""
    return _skill_manager


def _build_skill_addendum(user_text: str) -> str:
    """每次 LLM 调用前生成 system prompt 补丁。manager 未启用时返回 ''。"""
    if _skill_manager is None:
        return ""
    try:
        return _skill_manager.build_addendum_for_message(user_text)
    except Exception:
        logger.exception("[VoiceSession] build_skill_addendum 失败")
        return ""


def shutdown_mcp() -> None:
    """供应用退出钩子调用"""
    global _mcp_manager
    if _mcp_manager is not None:
        try:
            _mcp_manager.shutdown()
        except Exception:
            logger.exception("[VoiceSession] MCP 关闭失败")
        finally:
            _mcp_manager = None


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
            agent_result = self._orchestrator.run(
                user_text=user_text,
                conversation_history=context_history,
                extra_system=_build_skill_addendum(user_text),
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
        from voice_assistant.agent.orchestrator import AgentEvent

        self._ensure_initialized()
        if not user_text.strip():
            yield AgentEvent(
                type="complete",
                result=ProcessResult(response="", intent_type="unknown", confidence=0.0),
            )
            return

        context_history = history if history is not None else list(self._history)

        if self._on_execution_start:
            self._on_execution_start()
        try:
            self._orchestrator._confirm_callback = self._confirm_callback
            for event in self._orchestrator.run_stream(
                user_text,
                conversation_history=context_history,
                extra_system=_build_skill_addendum(user_text),
            ):
                if event.type == "complete" and event.result:
                    response = event.result.response or "(无回复)"
                    self._append_history(user_text, response)
                    yield AgentEvent(
                        type="complete",
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
                type="error",
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
                pass

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

    def _trim_history(self):
        if len(self._history) > self._max_history_turns:
            self._history = self._history[-self._max_history_turns:]

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
            except Exception:
                pass
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
