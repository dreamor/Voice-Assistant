"""
Voice Assistant System Tests
"""
import os
import tempfile

import pytest


class TestImports:
    """Test all required imports"""

    def test_numpy(self):
        import numpy
        assert numpy is not None

    def test_soundfile(self):
        import soundfile
        assert soundfile is not None

    def test_edge_tts(self):
        import edge_tts
        assert edge_tts is not None

    def test_requests(self):
        import requests
        assert requests is not None

    def test_litellm(self):
        import litellm
        assert litellm is not None


class TestConfiguration:
    """Test configuration loading from config.yaml and .env"""

    def test_config_loads(self):
        from voice_assistant.config import config
        assert config is not None

    def test_asr_api_key(self):
        from voice_assistant.config import config
        assert config.asr.api_key is not None, "ASR_API_KEY not set"
        assert len(config.asr.api_key) > 0, "ASR_API_KEY is empty"

    def test_asr_model(self):
        from voice_assistant.config import config
        assert config.asr.model is not None, "ASR_MODEL not set"

    def test_asr_base_url(self):
        from voice_assistant.config import config
        assert config.asr.base_url is not None, "ASR_BASE_URL not set"
        assert config.asr.base_url.startswith("https://"), "ASR_BASE_URL should be HTTPS"

    def test_llm_api_key(self):
        """当前活跃 provider 必须有 api_key"""
        from voice_assistant.config import config
        provider = config.providers.providers[config.provider]
        assert provider.api_key is not None, f"{provider.api_key_env} not set"
        assert len(provider.api_key) > 0, f"{provider.api_key_env} is empty"

    def test_llm_model(self):
        from voice_assistant.config import config
        assert config.llm.model is not None, "LLM model not resolved"
        assert len(config.llm.model) > 0, "LLM model is empty"

    def test_llm_base_url(self):
        """当前活跃 provider 必须有合法 base_url（除非 provider 用默认 endpoint）"""
        from voice_assistant.config import config
        provider = config.providers.providers[config.provider]
        if provider.base_url:
            assert provider.base_url.startswith(("http://", "https://")), \
                f"provider {config.provider} base_url 协议非法"

    def test_sample_rate(self):
        from voice_assistant.config import config
        assert config.audio.sample_rate == 16000, "SAMPLE_RATE should be 16000 for ASR optimization"

    def test_tts_voice(self):
        from voice_assistant.config import config
        assert config.audio.tts.voice is not None, "tts.voice not set"
        assert len(config.audio.tts.voice) > 0, "tts.voice is empty"

    def test_vad_config(self):
        from voice_assistant.config import config
        assert config.vad.threshold is not None
        assert config.vad.silence_timeout is not None
        assert config.vad.min_speech is not None
        assert config.vad.wait_timeout is not None

    def test_asr_language_hints(self):
        from voice_assistant.config import config
        assert config.asr.language_hints is not None
        assert 'zh' in config.asr.language_hints
        assert 'en' in config.asr.language_hints

    def test_asr_disfluency_removal(self):
        from voice_assistant.config import config
        assert config.asr.disfluency_removal_enabled is not None

    def test_hotwords_config(self):
        from voice_assistant.config import config
        assert config.asr.hotwords is not None
        assert config.asr.hotwords.enabled is not None


class TestLLMAPI:
    """Test LLM API connection"""

    def test_llm_api_endpoint(self):
        import requests

        from voice_assistant.config import config

        provider = config.providers.providers[config.provider]
        if not provider.base_url:
            pytest.skip(f"provider {config.provider} 使用默认 endpoint，无法直接 GET /models")

        response = requests.get(
            f"{provider.base_url}/models",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            timeout=10
        )
        assert response.status_code == 200, f"LLM API returned {response.status_code}"


class TestCloudASR:
    """Test Cloud ASR functionality"""

    def test_cloud_asr_initialization(self):
        from voice_assistant.audio.cloud_asr import CloudASR
        asr = CloudASR()
        assert asr is not None
        assert asr.model is not None

    def test_cloud_asr_recognize_silence(self):
        import numpy as np
        import soundfile as sf

        from voice_assistant.audio.cloud_asr import CloudASR

        sample_rate = 16000  # 标准 ASR 采样率
        duration = 1
        t = np.linspace(0, duration, sample_rate * duration)
        frequency = 440
        audio_data = (np.sin(2 * np.pi * frequency * t) * 0.3).astype(np.float32)

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            sf.write(tmp.name, audio_data, sample_rate, format='WAV')
            test_file = tmp.name

        try:
            asr = CloudASR()
            result = asr.recognize_from_file(test_file)
            assert result is not None
        finally:
            os.unlink(test_file)


class TestEdgeTTS:
    """Test Edge TTS functionality"""

    def test_edge_tts_synthesis(self):
        from voice_assistant.audio.tts import synthesize

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            output_file = tmp.name

        try:
            result = synthesize("测试", output_file)
            assert result, "TTS synthesis failed"
            assert os.path.exists(output_file), "Output file not created"
            assert os.path.getsize(output_file) > 0, "Output file is empty"
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)


class TestAudioDevices:
    """Test audio device availability - skipped in CI/headless"""

    @pytest.mark.skip(reason="sounddevice removed, Web UI uses browser audio")
    def test_input_devices(self):
        pass

    @pytest.mark.skip(reason="sounddevice removed, Web UI uses browser audio")
    def test_output_devices(self):
        pass


class TestVoiceAssistantAI:
    """Test main module imports"""

    def test_module_loads(self):
        from voice_assistant import __main__
        assert __main__ is not None

    def test_modules_load(self):
        from voice_assistant.agent.orchestrator import AgentOrchestrator
        from voice_assistant.audio.cloud_asr import CloudASR
        from voice_assistant.audio.tts import synthesize
        from voice_assistant.config import config
        from voice_assistant.core.session import VoiceSession

        assert config is not None
        assert AgentOrchestrator is not None
        assert CloudASR is not None
        assert synthesize is not None
        assert VoiceSession is not None


class TestASRCorrector:
    """Test ASR correction functionality"""

    def test_corrector_imports(self):
        from voice_assistant.core.asr_corrector import _needs_correction, correct_asr_result
        assert correct_asr_result is not None
        assert _needs_correction is not None

    def test_needs_correction_detection(self):
        from voice_assistant.core.asr_corrector import _needs_correction

        # 技术相关内容应该需要纠错
        assert _needs_correction("帮我打开维埃斯扣的") is True
        assert _needs_correction("运行皮松脚本") is True

        # 包含英文的内容不需要纠错
        assert _needs_correction("Open VS Code") is False

    def test_short_text_no_correction(self):
        from voice_assistant.core.asr_corrector import correct_asr_result

        # 短文本不需要纠错
        result = correct_asr_result("好")
        assert result == "好"

    def test_corrector_with_history(self):
        from voice_assistant.core.asr_corrector import correct_asr_result

        # 带历史的纠错
        history = [
            {"role": "user", "content": "帮我打开 VS Code"},
            {"role": "assistant", "content": "好的，正在打开 VS Code"}
        ]
        result = correct_asr_result("运行皮松脚本", history)
        assert result is not None


class TestSecurityUtils:
    """Test security utilities"""

    def test_security_imports(self):
        from voice_assistant.security.validation import (
            rate_limit,
            validate_audio_input,
            validate_text_input,
        )
        assert validate_text_input is not None
        assert validate_audio_input is not None
        assert rate_limit is not None

    def test_text_validation(self):
        from voice_assistant.security.validation import InputValidationError, validate_text_input

        # 正常文本
        result = validate_text_input("Hello World")
        assert result == "Hello World"

        # 空文本应该失败
        with pytest.raises(InputValidationError):
            validate_text_input("")

        # 过长文本应该失败
        with pytest.raises(InputValidationError):
            validate_text_input("x" * 2000)

    def test_audio_validation(self):
        from voice_assistant.security.validation import InputValidationError, validate_audio_input

        # 正常音频数据
        result = validate_audio_input(b"RIFF" + b"x" * 100)
        assert result == b"RIFF" + b"x" * 100

        # 空音频应该失败
        with pytest.raises(InputValidationError):
            validate_audio_input(b"")

    def test_rate_limit(self):
        from voice_assistant.security.validation import RateLimitError, rate_limit

        @rate_limit(calls=3, period=1.0)
        def test_func():
            return "ok"

        # 前 3 次应该成功
        for _ in range(3):
            assert test_func() == "ok"

        # 第 4 次应该失败
        with pytest.raises(RateLimitError):
            test_func()

    def test_rate_limiter_class(self):
        from voice_assistant.security.validation import RateLimiter, RateLimitError

        limiter = RateLimiter(calls=2, period=1.0)

        # 前 2 次检查应该通过
        limiter.check()
        limiter.check()

        # 第 3 次应该失败
        with pytest.raises(RateLimitError):
            limiter.check()
