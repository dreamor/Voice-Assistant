"""
语音助手 - Open Interpreter 版本（重构后）
功能：麦克风收音 → STT → 意图识别 → 路由执行 → 语音反馈
支持本地/在线模型切换
"""
import io
import logging
import os

from voice_assistant.config import config
from voice_assistant.audio.vad import record_audio
from voice_assistant.audio.tts import synthesize
from voice_assistant.audio.player import play_audio
from voice_assistant.audio.cloud_asr import CloudASR
from voice_assistant.core.asr_corrector import correct_asr_result
import voice_assistant.core.ai_client as ai_client  # 导入以访问本地 LLM 客户端

# 导入新架构模块
from voice_assistant.model.intent import IntentType
from voice_assistant.executors.computer import ComputerExecutor
from voice_assistant.executors.chat import ChatExecutor
from voice_assistant.services.router import CommandRouter, simple_classify_intent

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

# 本地模型状态
_use_local_llm = config.llm.use_local
_use_multimodal_audio = config.llm.local.use_multimodal_audio


def toggle_multimodal_audio():
    """切换多模态音频模式"""
    global _use_multimodal_audio
    _use_multimodal_audio = not _use_multimodal_audio
    if _use_multimodal_audio and not _use_local_llm:
        logger.warning("多模态音频模式仅在本地模型模式下生效")
        _use_multimodal_audio = False
        return False, "关闭"
    return True, "开启" if _use_multimodal_audio else "关闭"


def toggle_llm_mode():
    """切换本地/在线 LLM 模式"""
    global _use_local_llm
    _use_local_llm = not _use_local_llm

    # 更新 ai_client 的行为
    # 注意：config 是 frozen dataclass，不能直接修改
    # 我们通过全局变量控制
    if _use_local_llm:
        # 尝试初始化本地客户端
        client = ai_client.get_local_llm_client(enable_audio=_use_multimodal_audio)
        if client is None:
            logger.warning("本地模型不可用，保持在线模式")
            _use_local_llm = False
            return False, "在线"
        return True, "本地"
    else:
        # 关闭本地客户端
        ai_client.close_local_llm_client()
        return True, "在线"


def get_llm_mode() -> str:
    """获取当前 LLM 模式"""
    return "本地" if _use_local_llm else "在线"


def recognize(audio_bytes) -> str:
    """语音识别（使用阿里云 ASR）+ 纠错"""
    try:
        result = asr_client.recognize_from_bytes(audio_bytes)

        if result and not result.startswith("云端ASR错误"):
            # 对识别结果进行纠错
            corrected = correct_asr_result(result, chat_executor.get_history())
            if corrected != result:
                logger.info(f"  [Corrected] {result} → {corrected}")
            return corrected
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

    import tempfile
    import os

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
        except:
            pass


def main():
    global _use_local_llm

    logger.info("\n" + "=" * 50)
    logger.info(f"  {config.name} v{config.version}")
    logger.info("=" * 50)
    logger.info(f"  ASR: {config.asr.model}")
    llm_mode = "本地" if _use_local_llm else "在线"
    llm_name = config.llm.local.model_name if _use_local_llm else config.llm.model
    logger.info(f"  LLM: {llm_name} ({llm_mode})")
    if _use_local_llm:
        multimodal_status = "ON" if _use_multimodal_audio else "OFF"
        logger.info(f"  Multimodal Audio: {multimodal_status}")
    logger.info("=" * 50)
    logger.info("  [ENTER] Start recording")
    logger.info("  [C]     Clear history")
    logger.info("  [H]     Show history")
    logger.info("  [I]     Toggle Auto/AI")
    logger.info("  [L]     Toggle Local/Online LLM")
    logger.info("  [M]     Toggle Multimodal Audio")
    logger.info("  [Q]     Quit")
    logger.info("=" * 50)
    logger.info("\nReady!\n")

    # True=自动模式（自动判断意图），False=强制 AI 对话
    auto_mode = True

    while True:
        mode = "自动" if auto_mode else "AI 对话"
        llm_mode = get_llm_mode()
        cmd = input(f"[ENTER=Record / C=Clear / H=History / I=Toggle / L=LLM / Q=Quit] (模式:{mode}, LLM:{llm_mode}): ").strip().lower()

        if cmd == 'q':
            # 清理资源
            ai_client.close_local_llm_client()
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
        elif cmd == 'l':
            success, new_mode = toggle_llm_mode()
            if success:
                logger.info(f"[OK] LLM 模式切换为: {new_mode}\n")
            else:
                logger.warning(f"[Failed] LLM 模式切换失败\n")
            continue
        elif cmd == 'm':
            success, new_mode = toggle_multimodal_audio()
            if success:
                logger.info(f"[OK] 多模态音频模式已: {new_mode}\n")
            else:
                logger.warning(f"[Failed] 多模态音频模式切换失败\n")
            continue

        logger.info("\n[Recording] Speak now...")
        audio = record_audio(max_seconds=config.vad.max_recording)

        if len(audio) < config.audio.sample_rate * 0.5:
            logger.warning("[Warning] Too short\n")
            continue

        logger.info(f"  [OK] Recorded {len(audio)/config.audio.sample_rate:.1f}s")

        # Write audio to temp WAV file (LiteRT needs a file path for multimodal input)
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_wav_path = tmp.name

        try:
            sf.write(tmp_wav_path, audio, config.audio.sample_rate, format='WAV')

            # 多模态模式：音频直接送 Gemma 4
            if _use_local_llm and _use_multimodal_audio:
                logger.info("\n[Step 1] Multimodal audio → Gemma 4...")
                full_response = []
                for chunk in ai_client.ask_ai_stream_with_audio("", tmp_wav_path):
                    full_response.append(chunk) if chunk else None
                    logger.info(f"\r  [AI] {chunk}", end='', flush=True)
                logger.info("")  # newline after streaming
                user_text = full_response[-1] if full_response else ""

                if not user_text.strip():
                    logger.warning("[Warning] 未从模型得到有效回复\n")
                    continue
                logger.info(f"  [Gemma] {user_text[:100]}...")
            else:
                # 传统流程：ASR → 文本 → LLM
                logger.info("\n[Step 1] Recognizing...")
                with io.BytesIO() as buf:
                    sf.write(buf, audio, config.audio.sample_rate, format='WAV')
                    audio_bytes = buf.getvalue()

                user_text = recognize(audio_bytes)
                logger.info(f"  You: {user_text}")

                if not user_text.strip():
                    logger.warning("[Warning] No speech detected\n")
                    continue

                logger.info("\n[Step 2] Processing...")

            logger.info("\n[Processing] Routing...")
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

        finally:
            try:
                os.unlink(tmp_wav_path)
            except Exception:
                pass


if __name__ == "__main__":
    main()