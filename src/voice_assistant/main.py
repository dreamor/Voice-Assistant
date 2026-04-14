"""
语音助手 - Open Interpreter 版本（重构后）
功能：麦克风收音 → STT → 意图识别 → 路由执行 → 语音反馈
本地 ASR 使用 FunASR，在线 ASR 使用阿里云 Paraformer
"""
import io
import logging
import os
import sys
import tempfile

import soundfile as sf

from voice_assistant.audio.cloud_asr import CloudASR
from voice_assistant.audio.player import play_audio
from voice_assistant.audio.tts import synthesize
from voice_assistant.audio.vad import record_audio
from voice_assistant.config import config
from voice_assistant.core.asr_corrector import correct_asr_result
from voice_assistant.core.dependencies import check_dependencies
from voice_assistant.executors.chat import ChatExecutor
from voice_assistant.executors.computer import ComputerExecutor
from voice_assistant.services.router import CommandRouter, simple_classify_intent

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.logging.level),
    format=config.logging.format
)
logger = logging.getLogger(__name__)


def check_startup_dependencies() -> bool:
    """启动时检查依赖

    Returns:
        True 如果可以启动，False 如果有必需依赖缺失
    """
    manager = check_dependencies(config, verbose=False)

    print("\n" + "=" * 50)
    print("  依赖检查")
    print("=" * 50)

    for result in manager.results:
        status_icon = {
            "available": "\u2713",
            "missing": "\u2717",
            "version_mismatch": "\u26a0",
            "not_required": "\u2299",
        }.get(result.status.value, "?")

        if result.installed_version:
            print(f"  {status_icon} {result.dependency.name}: {result.installed_version}")
        elif result.status.value == "not_required":
            print(f"  {status_icon} {result.dependency.name}: 跳过（配置未启用）")
        else:
            print(f"  {status_icon} {result.dependency.name}: 未安装")

    print("=" * 50)

    if manager.has_blocking_errors():
        print("\n\u274c 存在必需依赖缺失，无法启动\n")
        missing = manager.get_missing_dependencies()
        if missing:
            print("请安装以下依赖:")
            for dep in missing:
                print(f"  {dep.get_install_command()}")
            print()
        return False

    warnings = manager.get_version_warnings()
    if warnings:
        print("\n\u26a0 版本警告:")
        for r in warnings:
            print(f"  \u2022 {r.message}")
        print()

    print("\u2705 依赖检查通过\n")
    return True


# 初始化执行器
computer_executor = ComputerExecutor(
    auto_run=config.interpreter.auto_run,
    verbose=config.interpreter.verbose
)
chat_executor = ChatExecutor(max_response_length=200)

# 初始化路由器
router = CommandRouter(executors=[computer_executor, chat_executor])

# 初始化 ASR（本地/在线）
_use_local_asr = config.asr.use_local

if _use_local_asr:
    from voice_assistant.audio.funasr_asr import FUNASR_AVAILABLE, FunASRClient
    if FUNASR_AVAILABLE:
        asr_client_funasr = FunASRClient(
            model_path=config.asr.local.model_path,
            device=config.asr.local.device,
            vad_threshold=config.asr.local.vad_threshold,
        )
        logger.info("FunASR 本地 ASR 引擎已初始化")
    else:
        logger.warning("FunASR 未安装，回退到云端 ASR")
        _use_local_asr = False
        asr_client_cloud = CloudASR(
            api_key=config.asr.api_key, model=config.asr.model
        )
else:
    asr_client_cloud = CloudASR(
        api_key=config.asr.api_key, model=config.asr.model
    )
    logger.info(f"云端 ASR 已初始化 ({config.asr.model})")


def toggle_asr_mode():
    """切换本地/在线 ASR 模式"""
    global _use_local_asr
    _use_local_asr = not _use_local_asr

    if _use_local_asr:
        try:
            from voice_assistant.audio.funasr_asr import FUNASR_AVAILABLE, FunASRClient
            if FUNASR_AVAILABLE:
                global asr_client_funasr
                asr_client_funasr = FunASRClient(
                    model_path=config.asr.local.model_path,
                    device=config.asr.local.device,
                    vad_threshold=config.asr.local.vad_threshold,
                )
                return True, "本地"
            else:
                logger.warning("FunASR 未安装，无法切换到本地 ASR")
                _use_local_asr = False
                return False, "本地"
        except Exception as e:
            logger.error(f"切换到本地 ASR 失败: {e}")
            _use_local_asr = False
            return False, "本地"
    else:
        return True, "云端"


def get_asr_mode() -> str:
    """获取当前 ASR 模式"""
    return "本地" if _use_local_asr else "云端"


def recognize(audio_bytes) -> str:
    """语音识别（本地 FunASR 或阿里云 ASR）+ 纠错"""
    try:
        if _use_local_asr:
            result = asr_client_funasr.recognize_bytes(
                audio_bytes, sample_rate=config.audio.sample_rate
            )
        else:
            result = asr_client_cloud.recognize_from_bytes(audio_bytes)

        if result and not result.startswith("\u4e91\u7aefASR\u9519\u8bef") and not result.startswith("FunASR"):
            # 对识别结果进行纠错
            corrected = correct_asr_result(result, chat_executor.get_history())
            if corrected != result:
                logger.info(f"  [Corrected] {result} \u2192 {corrected}")
            return corrected
        else:
            logger.warning(f"  [Error] ASR failed: {result}")
            return ""
    except Exception as e:
        logger.error(f"  [Error] ASR error: {e}")
        return ""


def speak_and_play(text: str):
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
        except Exception:
            pass


def main():
    global _use_local_asr

    # 启动时检查依赖
    if not check_startup_dependencies():
        sys.exit(1)

    logger.info("\n" + "=" * 50)
    logger.info(f"  {config.name} v{config.version}")
    logger.info("=" * 50)
    asr_mode = "\u672c\u5730 FunASR" if _use_local_asr else f"\u4e91\u7aef {config.asr.model}"
    logger.info(f"  ASR: {asr_mode}")
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

    # True=自动模式（自动判断意图），False=强制 AI 对话
    auto_mode = True

    while True:
        mode = "\u81ea\u52a8" if auto_mode else "AI \u5bf9\u8bdd"
        asr_mode_str = get_asr_mode()
        cmd = input(f"[ENTER=Record / C=Clear / H=History / I=Toggle / A=ASR / Q=Quit] (\u6a21\u5f0f:{mode}, ASR:{asr_mode_str}): ").strip().lower()

        if cmd == 'q':
            # 清理资源
            if _use_local_asr:
                asr_client_funasr.close()
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
        elif cmd == 'a':
            success, new_mode = toggle_asr_mode()
            if success:
                logger.info(f"[OK] ASR \u6a21\u5f0f\u5207\u6362\u4e3a: {new_mode}\n")
            else:
                logger.warning("[Failed] ASR \u6a21\u5f0f\u5207\u6362\u5931\u8d25\n")
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
        user_text = recognize(audio_bytes)
        logger.info(f"  You: {user_text}")

        if not user_text.strip():
            logger.warning("[Warning] No speech detection\n")
            continue

        logger.info("\n[Step 2] Processing...")
        logger.info("\n[Processing] Routing...")
        if auto_mode:
            # 自动模式：意图识别 + 路由
            intent = simple_classify_intent(user_text)
            logger.info(f"  [Intent] {intent.intent_type.value} (confidence: {intent.confidence})")
            context = {'history': chat_executor.get_history()}
            result = router.route(intent, context)
            reply = result.get('response', '\u62b1\u6b49\uff0c\u6ca1\u6709\u7406\u89e3')
            # 更新历史
            if 'history_updated' in result:
                chat_executor._conversation_history = result['history_updated']
        else:
            # 强制 AI 对话模式
            result = chat_executor.execute(user_text)
            reply = result.get('response', '\u62b1\u6b49\uff0c\u53d1\u751f\u9519\u8bef')

        logger.info(f"  Reply: {reply[:200]}...")

        logger.info("\n[Step 3] Speaking...")
        speak_and_play(reply)
        logger.info("\n" + "-" * 50 + "\n")


if __name__ == "__main__":
    main()
