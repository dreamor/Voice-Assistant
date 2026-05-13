# ruff: noqa: E402
"""端到端测试热词：TTS 合成 → ASR 识别 → 校验关键词。"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from voice_assistant.audio.cloud_asr import CloudASR
from voice_assistant.audio.tts import EdgeTTSProvider

TEST_PHRASES = [
    ("请打开 Open Interpreter", "Open Interpreter"),
    ("我要用 FastAPI 写一个 Vue.js 项目", "FastAPI"),
    ("用 PostgreSQL 配合 Redis 做缓存", "PostgreSQL"),
    ("调用 GraphQL 接口", "GraphQL"),
]


def mp3_to_wav16k(mp3_bytes: bytes) -> bytes:
    import io

    from pydub import AudioSegment
    seg = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    seg = seg.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    out = io.BytesIO()
    seg.export(out, format="wav")
    return out.getvalue()


def main() -> int:
    asr = CloudASR()
    print(f"[INFO] vocabulary_id: {asr._vocabulary_id}\n")
    tts = EdgeTTSProvider(voice="zh-CN-XiaoxiaoNeural")
    passed = failed = 0

    for text, keyword in TEST_PHRASES:
        print(f"[TEST] 原文: {text}")
        try:
            mp3 = tts.synthesize_to_bytes(text)
            if not mp3:
                print("  [FAIL] TTS 返回空")
                failed += 1
                continue
            wav = mp3_to_wav16k(mp3)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav)
                wav_path = f.name
            recognized = asr.recognize_from_file(wav_path)
            os.unlink(wav_path)
            print(f"  识别: {recognized}")
            if keyword.lower() in (recognized or "").lower():
                print(f"  [PASS] 命中 '{keyword}'")
                passed += 1
            else:
                print(f"  [FAIL] 未命中 '{keyword}'")
                failed += 1
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            failed += 1
        print()

    print("=" * 40)
    print(f"  PASS: {passed}/{len(TEST_PHRASES)}   FAIL: {failed}")
    print("=" * 40)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

