"""
Voice Assistant 应用核心类
统一的 lifecycle 管理：初始化 → 运行 → 清理
消除 main.py 的模块级全局变量和散落的资源清理
"""
import io
import logging
import os
import signal
import sys
import tempfile
from typing import Optional

import soundfile as sf

from voice_assistant.config import config
from voice_assistant.audio.asr_provider import ASRProvider, create_asr_provider
from voice_assistant.audio.player import play_audio
from voice_assistant.audio.tts import synthesize
from voice_assistant.audio.vad import record_audio
from voice_assistant.core.asr_corrector import correct_asr_result
from voice_assistant.core.dependencies import check_dependencies
from voice_assistant.executors.chat import ChatExecutor
from voice_assistant.executors.computer import ComputerExecutor
from voice_assistant.services.router import CommandRouter, simple_classify_intent
from voice_assistant.model.intent import IntentType

logger = logging.getLogger(__name__)


class VoiceAssistant:
    """语音助手应用类
    
    封装所有组件的生命周期，提供统一的初始化、运行、清理接口。
    替代 main.py 中的模块级全局变量。
    """

    def __init__(self):
        self._asr: Optional[ASRProvider] = None
        self._chat_executor: Optional[ChatExecutor] = None
        self._computer_executor: Optional[ComputerExecutor] = None
        self._router: Optional[CommandRouter] = None
        self._auto_mode: bool = True
        self._initialized: bool = False

    def initialize(self) -> bool:
        """初始化所有组件
        
        Returns:
            True 如果初始化成功，False 如果有必需依赖缺失
        """
        # 依赖检查
        manager = check_dependencies(config, verbose=False)
        if manager.has_blocking_errors():
            self._print_dependency_report(manager)
            return False

        # 初始化 ASR
        try:
            self._asr = create_asr_provider(config)
        except Exception as e:
            logger.error(f"ASR 初始化失败: {e}")
            return False

        # 初始化执行器
        self._computer_executor = ComputerExecutor(
            auto_run=config.interpreter.auto_run,
            verbose=config.interpreter.verbose
        )
        self._chat_executor = ChatExecutor(max_response_length=200)

        # 初始化路由器
        self._router = CommandRouter(
            executors=[self._computer_executor, self._chat_executor]
        )

        self._initialized = True
        return True

    def recognize(self, audio_bytes: bytes) -> str:
        """语音识别 + 纠错
        
        ASR 提供者现在通过异常报告错误（而非返回错误字符串），
        所以成功时 result 就是识别文本，失败时由 except 捕获。
        """
        if not self._asr:
            logger.error("ASR 未初始化")
            return ""

        try:
            result = self._asr.recognize_bytes(audio_bytes, sample_rate=config.audio.sample_rate)

            if result:
                # 对识别结果进行纠错
                corrected = correct_asr_result(result, self._chat_executor.get_history())
                if corrected != result:
                    logger.info(f"  [Corrected] {result} → {corrected}")
                return corrected
            else:
                logger.warning("  [Warning] ASR returned empty result")
                return ""
        except Exception as e:
            logger.error(f"  [Error] ASR error: {e}")
            return ""

    def speak_and_play(self, text: str):
        """语音合成并播放"""
        if not text:
            return
        logger.info(f"  [Speaking] {text[:50]}...")

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if synthesize(text, tmp_path):
                with open(tmp_path, 'rb') as f:
                    audio_data = f.read()
                logger.info(f"  [OK] {len(audio_data)} bytes")
                logger.info("  [Playing]")
                play_audio(audio_data)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def process_text(self, user_text: str) -> str:
        """处理用户文本输入（意图识别 → 路由执行）

        Args:
            user_text: 用户输入文本

        Returns:
            AI 回复文本
        """
        if not self._initialized:
            return "助手未初始化"

        if self._auto_mode:
            intent = simple_classify_intent(user_text)
            logger.info(f"  [Intent] {intent.intent_type.value} (confidence: {intent.confidence})")
            context = {'history': self._chat_executor.get_history()}
            result = self._router.route(intent, context)
            reply = result.get('response', '抱歉，没有理解')
            # 更新历史
            if 'history_updated' in result:
                self._chat_executor._conversation_history = result['history_updated']
        else:
            result = self._chat_executor.execute(user_text)
            reply = result.get('response', '抱歉，发生错误')

        return reply

    @property
    def auto_mode(self) -> bool:
        return self._auto_mode

    @auto_mode.setter
    def auto_mode(self, value: bool):
        self._auto_mode = value

    @property 
    def chat_executor(self) -> Optional[ChatExecutor]:
        return self._chat_executor

    @property
    def router(self) -> Optional[CommandRouter]:
        return self._router

    def toggle_asr_mode(self) -> tuple[bool, str]:
        """切换本地/在线 ASR 模式
        
        Returns:
            (success, mode_name)
        """
        try:
            # 关闭当前 ASR
            if self._asr:
                self._asr.close()

            # 切换配置
            config.asr.use_local = not config.asr.use_local

            # 创建新的 ASR 提供者
            self._asr = create_asr_provider(config)
            mode = "本地" if config.asr.use_local else "云端"
            return True, mode
        except Exception as e:
            logger.error(f"ASR 模式切换失败: {e}")
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

    def clear_history(self):
        """清除对话历史"""
        if self._chat_executor:
            self._chat_executor.clear_history()

    def cleanup(self):
        """清理所有资源"""
        logger.info("[Cleanup] 正在清理资源...")
        
        if self._asr:
            try:
                self._asr.close()
                logger.info("[Cleanup] ASR 已关闭")
            except Exception as e:
                logger.warning(f"[Cleanup] ASR 关闭异常: {e}")

        # 关闭 pygame mixer
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.quit()
                logger.info("[Cleanup] pygame mixer 已关闭")
        except Exception:
            pass

        self._initialized = False
        logger.info("[Cleanup] 资源清理完成")

    def _print_dependency_report(self, manager):
        """打印依赖检查报告"""
        print("\n" + "=" * 50)
        print("  依赖检查")
        print("=" * 50)

        for result in manager.results:
            status_icon = {
                "available": "✓",
                "missing": "✗",
                "version_mismatch": "⚠",
                "not_required": "⊙",
            }.get(result.status.value, "?")

            if result.installed_version:
                print(f"  {status_icon} {result.dependency.name}: {result.installed_version}")
            elif result.status.value == "not_required":
                print(f"  {status_icon} {result.dependency.name}: 跳过（配置未启用）")
            else:
                print(f"  {status_icon} {result.dependency.name}: 未安装")

        print("=" * 50)

        if manager.has_blocking_errors():
            print("\n❌ 存在必需依赖缺失，无法启动\n")
            missing = manager.get_missing_dependencies()
            if missing:
                print("请安装以下依赖:")
                for dep in missing:
                    print(f"  {dep.get_install_command()}")
                print()

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
