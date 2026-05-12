"""
VoiceSession - 统一的语音会话管理

抽取 CLI 和 Web UI 的共同逻辑：
- ASR 语音识别（含纠错）
- LLM Agent Loop（意图识别 + function calling + 确定性 tool 执行）
- TTS 语音合成
- 对话历史管理
"""
import logging
import tempfile
import os
from typing import Optional, Callable
from dataclasses import dataclass, field

from voice_assistant.config import config
from voice_assistant.audio.asr_provider import ASRProvider, create_asr_provider
from voice_assistant.audio.tts import TTSProvider, create_tts_provider
from voice_assistant.core.asr_corrector import correct_asr_result
from voice_assistant.executors.chat import ChatExecutor
from voice_assistant.executors.computer import ComputerExecutor
from voice_assistant.services.router import CommandRouter, simple_classify_intent

logger = logging.getLogger(__name__)


def _build_tool_registry():
    """根据配置构建 ToolRegistry（延迟导入避免循环依赖）"""
    from voice_assistant.tools.registry import ToolRegistry
    from voice_assistant.tools.universal import get_universal_tools
    from voice_assistant.tools.platform_specific import get_platform_tools
    from voice_assistant.security.safe_guard import SafeGuard, ToolPolicy, SecurityLevel
    from voice_assistant.platform import detect_platform

    guard = SafeGuard(
        policies=[
            ToolPolicy(tool_name=name, blocked=True)
            for name in config.tools.blocked
        ] + [
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
    logger.info(f"[VoiceSession] 注册 {len(registry.list_tools())} 个工具 (platform={platform})")
    return registry


@dataclass
class ProcessResult:
    """处理结果"""
    response: str
    intent_type: str
    confidence: float
    execution_output: Optional[str] = None
    history_updated: bool = False


class VoiceSession:
    """统一的语音会话管理

    供 CLI 和 Web UI 共用，封装：
    - ASR 识别 + 纠错
    - 意图识别 + Agent Loop / Chat 路由
    - TTS 合成
    - 对话历史
    """

    def __init__(
        self,
        auto_mode: bool = True,
        max_response_length: int = 200,
        execution_timeout: float = 60.0,
        on_intent_detected: Optional[Callable[[str, float], None]] = None,
        on_execution_start: Optional[Callable[[], None]] = None,
        on_execution_end: Optional[Callable[[], None]] = None,
    ):
        """初始化会话

        Args:
            auto_mode: 是否自动模式（自动识别意图路由）
            max_response_length: Chat 执行器最大响应长度
            execution_timeout: 执行超时时间（秒）
            on_intent_detected: 意图检测回调
            on_execution_start: 执行开始回调
            on_execution_end: 执行结束回调
        """
        self._auto_mode = auto_mode
        self._max_response_length = max_response_length
        self._execution_timeout = execution_timeout

        # 回调
        self._on_intent_detected = on_intent_detected
        self._on_execution_start = on_execution_start
        self._on_execution_end = on_execution_end

        # 确认回调（由 Web UI 设置）
        self._confirm_callback: Optional[Callable[[str, dict, object], bool]] = None

        # 组件（延迟初始化）
        self._asr: Optional[ASRProvider] = None
        self._tts: Optional[TTSProvider] = None
        self._chat_executor: Optional[ChatExecutor] = None
        self._computer_executor: Optional[ComputerExecutor] = None
        self._router: Optional[CommandRouter] = None
        self._orchestrator = None  # AgentOrchestrator, 延迟导入避免循环依赖
        self._initialized = False

    def initialize(self) -> bool:
        """初始化组件

        Returns:
            True 如果成功，False 如果失败
        """
        try:
            # 初始化 ASR
            self._asr = create_asr_provider(config)

            # 初始化 TTS
            self._tts = create_tts_provider(config)

            # 初始化执行器
            self._computer_executor = ComputerExecutor(
                auto_run=config.interpreter.auto_run,
                verbose=config.interpreter.verbose
            )
            self._chat_executor = ChatExecutor(max_response_length=self._max_response_length)

            # 初始化路由器（保留作为 fallback）
            self._router = CommandRouter(
                executors=[self._computer_executor, self._chat_executor]
            )

            # 初始化 Agent Orchestrator（延迟导入避免循环依赖）
            try:
                from voice_assistant.agent.orchestrator import AgentOrchestrator
                tool_registry = _build_tool_registry()
                self._orchestrator = AgentOrchestrator(
                    tool_registry=tool_registry,
                    max_iterations=config.agent.max_iterations,
                )
                logger.info("[VoiceSession] AgentOrchestrator 初始化成功")
            except Exception as e:
                logger.warning(f"[VoiceSession] AgentOrchestrator 初始化失败，将使用 fallback: {e}")
                self._orchestrator = None

            self._initialized = True
            logger.info("[VoiceSession] 初始化成功")
            return True

        except Exception as e:
            logger.error(f"[VoiceSession] 初始化失败: {e}")
            return False
    
    def _ensure_initialized(self):
        """确保已初始化"""
        if not self._initialized:
            raise RuntimeError("VoiceSession 未初始化，请先调用 initialize()")
    
    @property
    def auto_mode(self) -> bool:
        return self._auto_mode
    
    @auto_mode.setter
    def auto_mode(self, value: bool):
        self._auto_mode = value
    
    def recognize(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """语音识别 + 纠错
        
        Args:
            audio_bytes: 音频数据（WAV 格式）
            sample_rate: 采样率
            
        Returns:
            识别文本（已纠错）
        """
        self._ensure_initialized()
        
        if not self._asr:
            logger.error("[VoiceSession] ASR 未初始化")
            return ""
        
        try:
            result = self._asr.recognize_bytes(audio_bytes, sample_rate=sample_rate)
            
            if result:
                # 纠错
                corrected = correct_asr_result(result, self.get_history())
                if corrected != result:
                    logger.info(f"  [Corrected] {result} → {corrected}")
                return corrected
            else:
                logger.warning("[VoiceSession] ASR 返回空结果")
                return ""
                
        except Exception as e:
            logger.error(f"[VoiceSession] ASR 错误: {e}")
            return ""
    
    def process_text(self, user_text: str, history: Optional[list] = None) -> ProcessResult:
        """处理用户文本（意图识别 + Agent Loop / Chat 路由）

        Args:
            user_text: 用户输入文本
            history: 可选的历史记录（用于 Web UI 传入数据库历史）

        Returns:
            ProcessResult 包含响应、意图类型、置信度等
        """
        self._ensure_initialized()

        if not user_text.strip():
            return ProcessResult(
                response="",
                intent_type="unknown",
                confidence=0.0
            )

        # 使用传入的历史或内部历史
        context_history = history if history is not None else self.get_history()

        if self._auto_mode:
            # 意图识别（轻量分类，决定走 Agent Loop 还是纯对话）
            intent = simple_classify_intent(user_text)

            # 回调
            if self._on_intent_detected:
                self._on_intent_detected(intent.intent_type.value, intent.confidence)

            logger.info(f"[VoiceSession] Intent: {intent.intent_type.value} (confidence: {intent.confidence})")

            if intent.intent_type.value == 'computer_control' and self._orchestrator:
                # Agent Loop 路径
                return self._process_with_agent(user_text, context_history)
            else:
                # Chat / Query 路径
                return self._process_with_chat(user_text, context_history)
        else:
            # 纯对话模式
            result = self._chat_executor.execute(user_text)
            return ProcessResult(
                response=result.get('response', '抱歉，发生错误'),
                intent_type='chat',
                confidence=1.0
            )

    def _process_with_agent(self, user_text: str, history: list) -> ProcessResult:
        """通过 AgentOrchestrator 处理电脑控制指令"""
        from voice_assistant.agent.orchestrator import AgentResult

        if self._on_execution_start:
            self._on_execution_start()

        try:
            # 注入确认回调
            self._orchestrator._confirm_callback = self._confirm_callback

            agent_result: AgentResult = self._orchestrator.run(
                user_text=user_text,
                conversation_history=history,
            )

            response = agent_result.response
            if agent_result.fallback_used:
                response += "\n（部分操作使用了 Open Interpreter 兜底）"

            # 将 agent 对话历史同步到 chat executor
            self._chat_executor._conversation_history = history + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": response},
            ]

            return ProcessResult(
                response=response,
                intent_type='computer',
                confidence=1.0,
                execution_output=", ".join(agent_result.tool_calls_made) if agent_result.tool_calls_made else None,
                history_updated=True,
            )
        except Exception as e:
            logger.error(f"[VoiceSession] Agent 循环失败: {e}")
            # Fallback 到旧路由
            logger.info("[VoiceSession] 回退到 CommandRouter")
            context = {'history': history}
            result = self._router.route(
                simple_classify_intent(user_text), context
            )
            return ProcessResult(
                response=result.get('response', '抱歉，处理失败'),
                intent_type='computer',
                confidence=0.5,
                execution_output=result.get('execution_output'),
                history_updated='history_updated' in result,
            )
        finally:
            if self._on_execution_end:
                self._on_execution_end()

    def _process_with_chat(self, user_text: str, history: list) -> ProcessResult:
        """通过 ChatExecutor 处理对话/查询"""
        context = {'history': history}
        result = self._router.route(
            simple_classify_intent(user_text), context
        )

        response = result.get('response', '抱歉，我没有理解你的请求')
        execution_output = result.get('execution_output')

        if 'history_updated' in result:
            self._chat_executor._conversation_history = result['history_updated']

        intent = simple_classify_intent(user_text)
        return ProcessResult(
            response=response,
            intent_type=intent.intent_type.value,
            confidence=intent.confidence,
            execution_output=execution_output,
            history_updated='history_updated' in result,
        )

    def process_text_stream(self, user_text: str, history: Optional[list] = None):
        """流式处理用户文本（生成 AgentEvent）

        当 Agent Loop 可用时，使用 orchestrator.run_stream() 逐事件 yield；
        否则回退到 process_text() 并包装为单个事件。

        Yields:
            AgentEvent: 流式事件（llm_token / tool_start / tool_result / complete / error）
        """
        from voice_assistant.agent.orchestrator import AgentEvent

        self._ensure_initialized()

        if not user_text.strip():
            yield AgentEvent(type="complete", result=ProcessResult(
                response="", intent_type="unknown", confidence=0.0
            ))
            return

        context_history = history if history is not None else self.get_history()

        if self._auto_mode:
            intent = simple_classify_intent(user_text)

            if self._on_intent_detected:
                self._on_intent_detected(intent.intent_type.value, intent.confidence)

            logger.info(f"[VoiceSession] Stream Intent: {intent.intent_type.value} (confidence: {intent.confidence})")

            if intent.intent_type.value == 'computer_control' and self._orchestrator:
                yield from self._process_with_agent_stream(user_text, context_history)
            else:
                # Chat 路径：回退到同步处理，包装为单个 complete 事件
                result = self._process_with_chat(user_text, context_history)
                yield AgentEvent(type="complete", result=result)
        else:
            result = self._chat_executor.execute(user_text)
            yield AgentEvent(type="complete", result=ProcessResult(
                response=result.get('response', '抱歉，发生错误'),
                intent_type='chat',
                confidence=1.0,
            ))

    def _process_with_agent_stream(self, user_text: str, history: list):
        """流式通过 AgentOrchestrator 处理电脑控制指令"""
        from voice_assistant.agent.orchestrator import AgentEvent, AgentResult

        if self._on_execution_start:
            self._on_execution_start()

        try:
            self._orchestrator._confirm_callback = self._confirm_callback

            accumulated_response = ""
            tool_calls_made = []

            for event in self._orchestrator.run_stream(user_text, conversation_history=history):
                if event.type == "llm_token":
                    accumulated_response += (event.content or "")
                    yield event

                elif event.type == "tool_start":
                    tool_calls_made.append(event.tool_name or "")
                    yield event

                elif event.type == "tool_result":
                    yield event

                elif event.type == "complete":
                    # 将 AgentResult 转为 ProcessResult
                    agent_result = event.result
                    if agent_result:
                        response = agent_result.response
                        if agent_result.fallback_used:
                            response += "\n（部分操作使用了 Open Interpreter 兜底）"
                        # 同步历史
                        self._chat_executor._conversation_history = history + [
                            {"role": "user", "content": user_text},
                            {"role": "assistant", "content": response},
                        ]
                        process_result = ProcessResult(
                            response=response,
                            intent_type='computer',
                            confidence=1.0,
                            execution_output=", ".join(agent_result.tool_calls_made) if agent_result.tool_calls_made else None,
                            history_updated=True,
                        )
                        yield AgentEvent(type="complete", result=process_result)
                    else:
                        yield event

                elif event.type == "error":
                    yield event

        except Exception as e:
            logger.error(f"[VoiceSession] Stream Agent 循环失败: {e}")
            # Fallback 到同步路径
            result = self._process_with_agent(user_text, history)
            yield AgentEvent(type="complete", result=result)

        finally:
            if self._on_execution_end:
                self._on_execution_end()

    def synthesize(self, text: str) -> Optional[bytes]:
        """语音合成

        Args:
            text: 要合成的文本

        Returns:
            音频数据（MP3 格式）或 None
        """
        if not text:
            return None

        # 优先使用 TTS Provider 的 synthesize_to_bytes
        if self._tts:
            try:
                result = self._tts.synthesize_to_bytes(text)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"[VoiceSession] TTS synthesize_to_bytes 失败，回退到文件模式: {e}")

        # 回退：使用文件模式
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if self._tts:
                success = self._tts.synthesize(text, tmp_path)
            else:
                # 最终回退：使用模块级函数
                from voice_assistant.audio.tts import synthesize as _synthesize
                success = _synthesize(text, tmp_path)

            if success and os.path.exists(tmp_path):
                with open(tmp_path, 'rb') as f:
                    return f.read()
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def synthesize_stream(self, text: str):
        """流式语音合成：逐句 yield 音频数据

        Args:
            text: 要合成的文本

        Yields:
            bytes: 音频数据块（MP3 格式）
        """
        if not text or not text.strip():
            return

        self._ensure_initialized()

        if self._tts and hasattr(self._tts, 'synthesize_stream'):
            try:
                yield from self._tts.synthesize_stream(text)
            except Exception as e:
                logger.warning(f"[VoiceSession] 流式TTS失败，回退到普通模式: {e}")
                # 回退：整体合成后 yield
                result = self.synthesize(text)
                if result:
                    yield result
        else:
            # Provider 不支持流式，回退到普通模式
            result = self.synthesize(text)
            if result:
                yield result
    
    def get_history(self) -> list:
        """获取对话历史"""
        if self._chat_executor:
            return self._chat_executor.get_history()
        return []
    
    def set_history(self, history: list):
        """设置对话历史（用于 Web UI 加载数据库历史）"""
        if self._chat_executor:
            self._chat_executor._conversation_history = history
    
    def clear_history(self):
        """清空对话历史"""
        if self._chat_executor:
            self._chat_executor.clear_history()
    
    def toggle_asr_mode(self) -> tuple[bool, str]:
        """切换本地/云端 ASR 模式
        
        Returns:
            (success, mode_name)
        """
        try:
            if self._asr:
                self._asr.close()
            
            config.asr.use_local = not config.asr.use_local
            self._asr = create_asr_provider(config)
            
            mode = "本地" if config.asr.use_local else "云端"
            return True, mode
            
        except Exception as e:
            logger.error(f"[VoiceSession] ASR 模式切换失败: {e}")
            # 回退到云端
            try:
                config.asr.use_local = False
                from voice_assistant.audio.cloud_asr import CloudASR
                self._asr = CloudASR(api_key=config.asr.api_key, model=config.asr.model)
            except Exception:
                pass
            return False, "云端"
    
    def get_asr_mode(self) -> str:
        """获取当前 ASR 模式"""
        return "本地" if config.asr.use_local else "云端"
    
    def cleanup(self):
        """清理资源"""
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
