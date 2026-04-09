"""
Voice Assistant System Tests
"""
import os
import tempfile

import pytest
from dotenv import load_dotenv

load_dotenv()


class TestImports:
    """Test all required imports"""

    def test_numpy(self):
        import numpy
        assert numpy is not None

    def test_sounddevice(self):
        import sounddevice
        assert sounddevice is not None

    def test_soundfile(self):
        import soundfile
        assert soundfile is not None

    def test_pygame(self):
        import pygame
        assert pygame is not None

    def test_edge_tts(self):
        import edge_tts
        assert edge_tts is not None

    def test_requests(self):
        import requests
        assert requests is not None

    def test_cloud_asr(self):
        import cloud_asr
        assert cloud_asr is not None


class TestConfiguration:
    """Test configuration loading from .env"""

    def test_asr_api_key(self):
        api_key = os.getenv("ASR_API_KEY")
        assert api_key is not None, "ASR_API_KEY not set"
        assert len(api_key) > 0, "ASR_API_KEY is empty"

    def test_asr_model(self):
        model = os.getenv("ASR_MODEL")
        assert model is not None, "ASR_MODEL not set"

    def test_asr_base_url(self):
        base_url = os.getenv("ASR_BASE_URL")
        assert base_url is not None, "ASR_BASE_URL not set"
        assert base_url.startswith("https://"), "ASR_BASE_URL should be HTTPS"

    def test_llm_api_key(self):
        api_key = os.getenv("LLM_API_KEY")
        assert api_key is not None, "LLM_API_KEY not set"
        assert len(api_key) > 0, "LLM_API_KEY is empty"

    def test_llm_model(self):
        model = os.getenv("LLM_MODEL")
        assert model is not None, "LLM_MODEL not set"

    def test_llm_base_url(self):
        base_url = os.getenv("LLM_BASE_URL")
        assert base_url is not None, "LLM_BASE_URL not set"
        assert base_url.startswith("https://"), "LLM_BASE_URL should be HTTPS"

    def test_sample_rate(self):
        sample_rate = os.getenv("SAMPLE_RATE")
        assert sample_rate is not None, "SAMPLE_RATE not set"
        assert sample_rate == "44100", "SAMPLE_RATE should be 44100"

    def test_edge_tts_voice(self):
        voice = os.getenv("EDGE_TTS_VOICE")
        assert voice is not None, "EDGE_TTS_VOICE not set"

    def test_vad_config(self):
        threshold = os.getenv("VAD_THRESHOLD")
        silence_timeout = os.getenv("VAD_SILENCE_TIMEOUT")
        min_speech = os.getenv("VAD_MIN_SPEECH")
        wait_timeout = os.getenv("VAD_WAIT_TIMEOUT")

        assert threshold is not None, "VAD_THRESHOLD not set"
        assert silence_timeout is not None, "VAD_SILENCE_TIMEOUT not set"
        assert min_speech is not None, "VAD_MIN_SPEECH not set"
        assert wait_timeout is not None, "VAD_WAIT_TIMEOUT not set"

    def test_ai_config(self):
        max_retries = os.getenv("AI_MAX_RETRIES")
        retry_delay = os.getenv("AI_RETRY_DELAY")

        assert max_retries is not None, "AI_MAX_RETRIES not set"
        assert retry_delay is not None, "AI_RETRY_DELAY not set"

    def test_system_prompt(self):
        prompt = os.getenv("SYSTEM_PROMPT")
        assert prompt is not None, "SYSTEM_PROMPT not set"
        assert len(prompt) > 0, "SYSTEM_PROMPT is empty"


class TestLLMAPI:
    """Test LLM API connection"""

    def test_llm_api_endpoint(self):
        import requests
        base_url = os.getenv("LLM_BASE_URL")
        api_key = os.getenv("LLM_API_KEY")

        response = requests.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        assert response.status_code == 200, f"LLM API returned {response.status_code}"


class TestCloudASR:
    """Test Cloud ASR functionality"""

    def test_cloud_asr_initialization(self):
        from cloud_asr import CloudASR
        asr = CloudASR()
        assert asr is not None
        assert asr.model is not None

    def test_cloud_asr_recognize_silence(self):
        from cloud_asr import CloudASR
        import numpy as np
        import soundfile as sf

        sample_rate = 44100
        duration = 1
        t = np.linspace(0, duration, sample_rate * duration)
        frequency = 440
        audio_data = (np.sin(2 * np.pi * frequency * t) * 0.3).astype(np.float32)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            sf.write(tmp.name, audio_data, sample_rate, format='WAV')
            test_file = tmp.name

        try:
            asr = CloudASR()
            result = asr.recognize_from_file(test_file, sample_rate)
            assert result is not None
        finally:
            os.unlink(test_file)


class TestEdgeTTS:
    """Test Edge-TTS functionality"""

    def test_edge_tts_synthesis(self):
        import edge_tts
        import asyncio

        async def test_synthesis():
            communicate = edge_tts.Communicate("测试", "zh-CN-XiaoxiaoNeural")
            audio = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio += chunk["data"]
            return len(audio)

        audio_len = asyncio.run(test_synthesis())
        assert audio_len > 0, "Edge-TTS generated no audio"


class TestAudioDevices:
    """Test audio input/output devices"""

    def test_input_devices(self):
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        assert len(input_devices) > 0, "No input devices found"

    def test_output_devices(self):
        import sounddevice as sd
        devices = sd.query_devices()
        output_devices = [d for d in devices if d['max_output_channels'] > 0]
        assert len(output_devices) > 0, "No output devices found"


class TestVoiceAssistantAI:
    """Test voice_assistant_ai module"""

    def test_module_loads(self):
        import voice_assistant_ai
        assert voice_assistant_ai is not None

    def test_modules_load(self):
        import vad
        import tts
        import ai_client
        import audio_player
        assert vad is not None
        assert tts is not None
        assert ai_client is not None
        assert audio_player is not None
