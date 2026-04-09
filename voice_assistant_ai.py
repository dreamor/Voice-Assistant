"""
语音助手 - Open Interpreter 版本（重构后）
功能：麦克风收音 → STT → 意图识别 → 路由执行 → 语音反馈
"""
import io
import logging

from config import config
from vad import record_audio
from tts import synthesize
from audio_player import play_audio
from cloud_asr import CloudASR

# 导入新架构模块
from models.intent import IntentType
from executors.computer_executor import ComputerExecutor
from executors.chat_executor import ChatExecutor
from services.router_service import CommandRouter, simple_classify_intent

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.logging.level),
    format=config.logging.format
)
logger = logging.getLogger(__name__)

# 初始化执行器
computer_executor = ComputerExecutor(
    auto_run=config.interpreter.auto_run,
    verbose=config.interpreter.verbose
)
chat_executor = ChatExecutor(max_response_length=200)

# 初始化路由器
router = CommandRouter(executors=[computer_executor, chat_executor])

# 初始化 ASR
asr_client = CloudASR(api_key=config.asr.api_key, model=config.asr.model)


def recognize(audio_bytes) -> str:
    """语音识别（使用阿里云 ASR）"""
    try:
        result = asr_client.recognize_from_bytes(audio_bytes)

        if result and not result.startswith("云端 ASR 错误"):
            return result
        else:
            logger.warning(f"  [Error] Cloud ASR failed: {result}")
            return ""
    except Exception as e:
        logger.error(f"  [Error] Cloud ASR error: {e}")
        return ""


def speak_and_play(text: str):
    """语音合成并播放"""
    if not text:
        return
    logger.info(f"  [Speaking] {text[:50]}...")
    audio_data = synthesize(text)
    logger.info(f"  [OK] {len(audio_data)} bytes")
    logger.info("  [Playing]")
    play_audio(audio_data)


def main():
    logger.info("\n" + "=" * 50)
    logger.info(f"  {config.name} v{config.version}")
    logger.info("=" * 50)
    logger.info(f"  ASR: {config.asr.model}")
    logger.info(f"  LLM: {config.llm.model}")
    logger.info("=" * 50)
    logger.info("  [ENTER] Start recording")
    logger.info("  [C]     Clear history")
    logger.info("  [H]     Show history")
    logger.info("  [I]     Toggle Auto/AI")
    logger.info("  [Q]     Quit")
    logger.info("=" * 50)
    logger.info("\nReady!\n")

    # True=自动模式（自动判断意图），False=强制 AI 对话
    auto_mode = True

    while True:
        mode = "自动" if auto_mode else "AI 对话"
        cmd = input(f"[ENTER=Record / C=Clear / H=History / I=Toggle / Q=Quit] (模式:{mode}): ").strip().lower()

        if cmd == 'q':
            logger.info("Bye!")
            break
        elif cmd == 'c':
            chat_executor.clear_history()
            logger.info("[OK] History cleared\n")
            continue
        elif cmd == 'h':
            history = chat_executor.get_history()
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
            auto_mode = not auto_mode
            logger.info(f"[OK] Switched to {mode}\n")
            continue

        logger.info("\n[Recording] Speak now...")
        audio = record_audio(max_seconds=config.vad.max_recording)

        if len(audio) < config.audio.sample_rate * 0.5:
            logger.warning("[Warning] Too short\n")
            continue

        logger.info(f"  [OK] Recorded {len(audio)/config.audio.sample_rate:.1f}s")

        logger.info("\n[Step 1] Recognizing...")
        with io.BytesIO() as buf:
            import soundfile as sf
            sf.write(buf, audio, config.audio.sample_rate, format='WAV')
            audio_bytes = buf.getvalue()

        user_text = recognize(audio_bytes)
        logger.info(f"  You: {user_text}")

        if not user_text.strip():
            logger.warning("[Warning] No speech detected\n")
            continue

        logger.info("\n[Step 2] Processing...")
        if auto_mode:
            # 自动模式：意图识别 + 路由
            intent = simple_classify_intent(user_text)
            logger.info(f"  [Intent] {intent.intent_type.value} (confidence: {intent.confidence})")
            context = {'history': chat_executor.get_history()}
            result = router.route(intent, context)
            reply = result.get('response', '抱歉，我没有理解')
            # 更新历史
            if 'history_updated' in result:
                chat_executor._conversation_history = result['history_updated']
        else:
            # 强制 AI 对话模式
            result = chat_executor.execute(user_text)
            reply = result.get('response', '抱歉，发生错误')

        logger.info(f"  Reply: {reply[:200]}...")

        logger.info("\n[Step 3] Speaking...")
        speak_and_play(reply)
        logger.info("\n" + "-" * 50 + "\n")


if __name__ == "__main__":
    main()