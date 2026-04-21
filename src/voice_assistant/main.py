"""
语音助手 - 主入口
功能：麦克风收音 → STT → 意图识别 → 路由执行 → 语音反馈
"""
import io
import logging
import signal
import sys

import soundfile as sf

from voice_assistant.config import config
from voice_assistant.app import VoiceAssistant

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.logging.level),
    format=config.logging.format
)
logger = logging.getLogger(__name__)

# 全局助手实例（用于信号处理）
_assistant: VoiceAssistant | None = None


def _signal_handler(signum, frame):
    """处理 Ctrl+C 信号，优雅关闭"""
    global _assistant
    logger.info("\n[Signal] 收到中断信号，正在退出...")
    if _assistant:
        _assistant.cleanup()
    sys.exit(0)


def main():
    """主入口"""
    global _assistant

    # 注册信号处理
    signal.signal(signal.SIGINT, _signal_handler)

    assistant = VoiceAssistant()
    _assistant = assistant

    # 初始化
    if not assistant.initialize():
        sys.exit(1)

    try:
        logger.info("\n" + "=" * 50)
        logger.info(f"  {config.name} v{config.version}")
        logger.info("=" * 50)
        logger.info(f"  ASR: {assistant.get_asr_mode()}")
        logger.info(f"  LLM: {config.llm.model}")
        logger.info("=" * 50)
        logger.info("  [ENTER] Start recording")
        logger.info("  [C]     Clear history")
        logger.info("  [H]     Show history")
        logger.info("  [I]     Toggle Auto/AI")
        logger.info("  [A]     Toggle ASR Local/Cloud")
        logger.info("  [Q]     Quit")
        logger.info("=" * 50)
        logger.info("\nReady!\n")

        while True:
            mode = "自动" if assistant.auto_mode else "AI 对话"
            asr_mode_str = assistant.get_asr_mode()
            cmd = input(
                f"[ENTER=Record / C=Clear / H=History / I=Toggle / A=ASR / Q=Quit] "
                f"(模式:{mode}, ASR:{asr_mode_str}): "
            ).strip().lower()

            if cmd == 'q':
                break
            elif cmd == 'c':
                assistant.clear_history()
                logger.info("[OK] History cleared\n")
                continue
            elif cmd == 'h':
                history = assistant.chat_executor.get_history()
                if history:
                    logger.info("\n--- History ---")
                    for i in range(0, len(history), 2):
                        if i + 1 < len(history):
                            logger.info(f"\n[Q] {history[i]['content']}")
                            logger.info(f"[A] {history[i+1]['content']}")
                    logger.info("\n--- End ---\n")
                else:
                    logger.info("[Info] No history\n")
                continue
            elif cmd == 'i':
                assistant.auto_mode = not assistant.auto_mode
                mode = "自动" if assistant.auto_mode else "AI 对话"
                logger.info(f"[OK] Switched to {mode}\n")
                continue
            elif cmd == 'a':
                success, new_mode = assistant.toggle_asr_mode()
                if success:
                    logger.info(f"[OK] ASR 模式切换为: {new_mode}\n")
                else:
                    logger.warning("[Failed] ASR 模式切换失败\n")
                continue

            logger.info("\n[Recording] Speak now...")
            audio = record_audio(max_seconds=config.vad.max_recording)

            if len(audio) < config.audio.sample_rate * 0.3:
                logger.warning("[Warning] Too short\n")
                continue

            logger.info(f"  [OK] Recorded {len(audio)/config.audio.sample_rate:.1f}s")

            with io.BytesIO() as buf:
                sf.write(buf, audio, config.audio.sample_rate, format='WAV')
                audio_bytes = buf.getvalue()

            logger.info("\n[Step 1] Recognizing...")
            user_text = assistant.recognize(audio_bytes)
            logger.info(f"  You: {user_text}")

            if not user_text.strip():
                logger.warning("[Warning] No speech detection\n")
                continue

            logger.info("\n[Step 2] Processing...")
            reply = assistant.process_text(user_text)
            logger.info(f"  Reply: {reply[:200]}...")

            logger.info("\n[Step 3] Speaking...")
            assistant.speak_and_play(reply)
            logger.info("\n" + "-" * 50 + "\n")

    except KeyboardInterrupt:
        logger.info("\n[Interrupted] 正在退出...")
    finally:
        assistant.cleanup()
        logger.info("Bye!")


if __name__ == "__main__":
    main()
