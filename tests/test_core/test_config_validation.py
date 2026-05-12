"""配置验证测试"""
import pytest
import os
from unittest.mock import patch

from voice_assistant.config import (
    AppConfig, ASRConfig, LLMConfig, AudioConfig, TTSConfig,
    VADConfig, HistoryConfig, IntentConfig,
    LoggingConfig, AgentConfig, ToolsConfig, HotwordsConfig, LocalASRConfig,
    _validate_config,
)


def _make_config(**overrides):
    """构建测试用 AppConfig，允许覆盖字段"""
    defaults = dict(
        name="test",
        version="1.0",
        asr=ASRConfig(
            model="test-model",
            base_url="http://localhost",
            api_key="test-key",
            language_hints=["zh"],
            disfluency_removal_enabled=False,
            max_sentence_silence=800,
            hotwords=HotwordsConfig(enabled=False, config_file="", vocabulary_id=None),
            use_local=False,
            local=LocalASRConfig(enabled=False, model_path=None, device="cpu", vad_threshold=0.5),
        ),
        llm=LLMConfig(
            model="test-model",
            base_url="http://localhost",
            api_key="test-key",
            max_tokens=2000,
            temperature=0.7,
        ),
        audio=AudioConfig(
            sample_rate=16000,
            edge_tts_voice="zh-CN-XiaoxiaoNeural",
            tts=TTSConfig(provider="edge-tts", voice="zh-CN-XiaoxiaoNeural"),
        ),
        vad=VADConfig(threshold=0.02, silence_timeout=1.5, min_speech=0.15, wait_timeout=10, max_recording=30),
        history=HistoryConfig(max_turns=20),
        intent=IntentConfig(model="test", timeout=5),
        logging=LoggingConfig(level="INFO", format="%(message)s"),
        agent=AgentConfig(max_iterations=5),
        tools=ToolsConfig(),
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


class TestValidateConfig:
    def test_valid_config_no_warnings(self):
        config = _make_config()
        warnings = _validate_config(config)
        assert warnings == []

    def test_missing_llm_api_key(self):
        config = _make_config(llm=LLMConfig(
            model="test", base_url="http://localhost", api_key="",
            max_tokens=2000, temperature=0.7,
        ))
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            _validate_config(config)

    def test_missing_asr_api_key_cloud_mode(self):
        config = _make_config(asr=ASRConfig(
            model="test", base_url="http://localhost", api_key="",
            language_hints=["zh"], disfluency_removal_enabled=False,
            max_sentence_silence=800,
            hotwords=HotwordsConfig(enabled=False, config_file="", vocabulary_id=None),
            use_local=False,
            local=LocalASRConfig(enabled=False, model_path=None, device="cpu", vad_threshold=0.5),
        ))
        with pytest.raises(ValueError, match="ASR_API_KEY"):
            _validate_config(config)

    def test_missing_asr_api_key_local_mode_ok(self):
        """本地模式不需要 ASR API key"""
        config = _make_config(asr=ASRConfig(
            model="test", base_url="http://localhost", api_key="",
            language_hints=["zh"], disfluency_removal_enabled=False,
            max_sentence_silence=800,
            hotwords=HotwordsConfig(enabled=False, config_file="", vocabulary_id=None),
            use_local=True,
            local=LocalASRConfig(enabled=True, model_path=None, device="cpu", vad_threshold=0.5),
        ))
        warnings = _validate_config(config)
        assert warnings == []

    def test_temperature_out_of_range(self):
        config = _make_config(llm=LLMConfig(
            model="test", base_url="http://localhost", api_key="test-key",
            max_tokens=2000, temperature=3.0,
        ))
        warnings = _validate_config(config)
        assert any("temperature" in w for w in warnings)

    def test_max_tokens_too_low(self):
        config = _make_config(llm=LLMConfig(
            model="test", base_url="http://localhost", api_key="test-key",
            max_tokens=0, temperature=0.7,
        ))
        with pytest.raises(ValueError, match="max_tokens"):
            _validate_config(config)

    def test_vad_threshold_out_of_range(self):
        config = _make_config(vad=VADConfig(
            threshold=1.5, silence_timeout=1.5, min_speech=0.15,
            wait_timeout=10, max_recording=30,
        ))
        warnings = _validate_config(config)
        assert any("threshold" in w for w in warnings)

    def test_non_standard_sample_rate(self):
        config = _make_config(audio=AudioConfig(
            sample_rate=96000,
            edge_tts_voice="zh-CN-XiaoxiaoNeural",
            tts=TTSConfig(provider="edge-tts", voice="zh-CN-XiaoxiaoNeural"),
        ))
        warnings = _validate_config(config)
        assert any("sample_rate" in w for w in warnings)

    def test_max_iterations_too_low(self):
        config = _make_config(agent=AgentConfig(max_iterations=0))
        with pytest.raises(ValueError, match="max_iterations"):
            _validate_config(config)

    def test_deprecated_edge_tts_voice(self):
        config = _make_config(audio=AudioConfig(
            sample_rate=16000,
            edge_tts_voice="zh-CN-YunxiNeural",
            tts=TTSConfig(provider="edge-tts", voice="zh-CN-YunxiNeural"),
        ))
        warnings = _validate_config(config)
        assert any("edge_tts_voice" in w for w in warnings)

    def test_unknown_tts_provider(self):
        config = _make_config(audio=AudioConfig(
            sample_rate=16000,
            edge_tts_voice="zh-CN-XiaoxiaoNeural",
            tts=TTSConfig(provider="unknown-tts", voice="test"),
        ))
        warnings = _validate_config(config)
        assert any("provider" in w for w in warnings)

    def test_history_max_turns_too_low(self):
        config = _make_config(history=HistoryConfig(max_turns=0))
        with pytest.raises(ValueError, match="max_turns"):
            _validate_config(config)