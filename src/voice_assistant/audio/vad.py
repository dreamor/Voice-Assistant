"""
VAD (Voice Activity Detection) 模块
语音活动检测，检测说话开始/结束
"""
import time
import numpy as np
import sounddevice as sd
from voice_assistant.config import config


def calculate_rms(audio_data):
    """计算音频的RMS能量"""
    if len(audio_data) == 0:
        return 0.0
    return np.sqrt(np.mean(audio_data ** 2))


def record_audio(max_seconds=None):
    """使用VAD录制音频，说完自动停止"""
    vad_cfg = config.vad
    audio_cfg = config.audio

    if max_seconds is None:
        max_seconds = vad_cfg.max_recording

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

        if rms > vad_cfg.threshold:
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
                if silence_duration >= vad_cfg.silence_timeout:
                    recording[0] = False
                    print(f"  [VAD] Silence timeout ({silence_duration:.1f}s)")

    stream = sd.InputStream(
        samplerate=audio_cfg.sample_rate,
        channels=1,
        dtype='float32',
        blocksize=CHUNK_SIZE,
        callback=callback
    )
    stream.start()

    print(f"  [VAD] Waiting for voice...")
    start_time = time.time()

    while not recording[0]:
        if time.time() - start_time > vad_cfg.wait_timeout:
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
        voice_duration = len(audio) / audio_cfg.sample_rate

        if has_voice[0] and voice_duration >= vad_cfg.min_speech:
            print(f"  [VAD] Recorded {voice_duration:.1f}s")
            return audio
        else:
            print(f"  [VAD] Audio too short")
            return np.array([])

    return np.array([])