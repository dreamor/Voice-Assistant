"""
Audio Player 模块
使用 pygame 播放音频
"""
import os
import time
import tempfile
import pygame


def play_audio(audio_data):
    """播放音频"""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        print("  [Playing] ...")
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.unload()
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass