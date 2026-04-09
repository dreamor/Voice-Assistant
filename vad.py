"""
VAD (Voice Activity Detection) 模块
语音活动检测，检测说话开始/结束
"""
import os
import time
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv()

VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD"))
VAD_SILENCE_TIMEOUT = float(os.getenv("VAD_SILENCE_TIMEOUT"))
VAD_MIN_SPEECH = float(os.getenv("VAD_MIN_SPEECH"))
VAD_WAIT_TIMEOUT = float(os.getenv("VAD_WAIT_TIMEOUT"))
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE"))


def calculate_rms(audio_data):
    """计算音频的RMS能量"""
    if len(audio_data) == 0:
        return 0.0
    return np.sqrt(np.mean(audio_data ** 2))


def record_audio(max_seconds=30):
    """使用VAD录制音频，说完自动停止"""
    frames = []
    recording = [False]
    silence_start = [None]
    has_voice = [False]
    CHUNK_SIZE = 1024

    def callback(indata, frames_count, time_info, _status):
        nonlocal frames, recording, silence_start, has_voice

        audio_chunk = indata[:, 0]
        rms = calculate_rms(audio_chunk)
        current_time = time.time()

        if rms > VAD_THRESHOLD:
            if not recording[0]:
                recording[0] = True
                print("  [VAD] Voice detected, starting recording...")

            silence_start[0] = None
            has_voice[0] = True

            if recording[0]:
                frames.append(indata.copy())
        else:
            if recording[0]:
                if silence_start[0] is None:
                    silence_start[0] = current_time

                silence_duration = current_time - silence_start[0]
                if silence_duration >= VAD_SILENCE_TIMEOUT:
                    recording[0] = False
                    print(f"  [VAD] Silence timeout ({silence_duration:.1f}s)")

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='float32',
        blocksize=CHUNK_SIZE,
        callback=callback
    )
    stream.start()

    print(f"  [VAD] Waiting for voice...")
    start_time = time.time()

    while not recording[0]:
        if time.time() - start_time > VAD_WAIT_TIMEOUT:
            print(f"  [VAD] Timeout waiting for voice")
            break
        time.sleep(0.1)

    recording_start = time.time()
    while recording[0]:
        if time.time() - recording_start > max_seconds:
            print(f"  [VAD] Max recording time reached")
            break
        time.sleep(0.1)

    stream.stop()
    stream.close()

    if frames:
        audio = np.concatenate(frames, axis=0).flatten()
        voice_duration = len(audio) / SAMPLE_RATE

        if has_voice[0] and voice_duration >= VAD_MIN_SPEECH:
            print(f"  [VAD] Recorded {voice_duration:.1f}s")
            return audio
        else:
            print(f"  [VAD] Audio too short")
            return np.array([])

    return np.array([])
