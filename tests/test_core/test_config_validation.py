"""配置验证测试"""

import pytest

from voice_assistant.config import (
    AgentConfig,
    AppConfig,
    ASRConfig,
    AudioConfig,
    HistoryConfig,
    HotwordsConfig,
    LLMConfig,
    LocalASRConfig,
    LoggingConfig,
    ProviderConfig,
    ProviderModelConfig,
    ProvidersConfig,
    ToolsConfig,
    TTSConfig,
    VADConfig,
    _resolve_active_provider,
    _validate_config,
)


def _make_providers(api_key_env: str = "DASHSCOPE_API_KEY") -> ProvidersConfig:
    return ProvidersConfig(providers={
        "dashscope": ProviderConfig(
            name="DashScope",
            litellm_prefix="openai",
            base_url="http://localhost",
            api_key_env=api_key_env,
            models=[ProviderModelConfig(id="test-model", name="Test Model")],
        ),
    })


@pytest.fixture(autouse=True)
def _set_dashscope_key(monkeypatch):
    """默认让 DASHSCOPE_API_KEY 存在，单个用例需要时再清掉"""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dummy")


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
            max_tokens=2000,
            temperature=0.7,
        ),
        audio=AudioConfig(
            sample_rate=16000,
            tts=TTSConfig(provider="edge-tts", voice="zh-CN-XiaoxiaoNeural"),
        ),
        vad=VADConfig(threshold=0.02, silence_timeout=1.5, min_speech=0.15, wait_timeout=10, max_recording=30),
        history=HistoryConfig(max_turns=20),
        logging=LoggingConfig(level="INFO", format="%(message)s"),
        agent=AgentConfig(max_iterations=5),
        tools=ToolsConfig(),
        providers=_make_providers(),
        provider="dashscope",
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


class TestValidateConfig:
    def test_valid_config_no_warnings(self):
        config = _make_config()
        warnings = _validate_config(config)
        assert warnings == []

    def test_missing_provider_api_key(self, monkeypatch):
        """当前 provider 的 api_key_env 未设置应抛错"""
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        config = _make_config()
        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
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
            model="test", max_tokens=2000, temperature=3.0,
        ))
        warnings = _validate_config(config)
        assert any("temperature" in w for w in warnings)

    def test_max_tokens_too_low(self):
        config = _make_config(llm=LLMConfig(
            model="test", max_tokens=0, temperature=0.7,
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
            tts=TTSConfig(provider="edge-tts", voice="zh-CN-XiaoxiaoNeural"),
        ))
        warnings = _validate_config(config)
        assert any("sample_rate" in w for w in warnings)

    def test_max_iterations_too_low(self):
        config = _make_config(agent=AgentConfig(max_iterations=0))
        with pytest.raises(ValueError, match="max_iterations"):
            _validate_config(config)

    def test_unknown_tts_provider(self):
        config = _make_config(audio=AudioConfig(
            sample_rate=16000,
            tts=TTSConfig(provider="unknown-tts", voice="test"),
        ))
        warnings = _validate_config(config)
        assert any("provider" in w for w in warnings)

    def test_history_max_turns_too_low(self):
        config = _make_config(history=HistoryConfig(max_turns=0))
        with pytest.raises(ValueError, match="max_turns"):
            _validate_config(config)


class TestResolveActiveProvider:
    """LLM_API_KEY 序号解析"""

    def _providers(self, *ids: str) -> ProvidersConfig:
        return ProvidersConfig(providers={
            pid: ProviderConfig(
                name=pid, litellm_prefix="openai", base_url=None,
                api_key_env=f"{pid.upper()}_API_KEY", models=[],
            ) for pid in ids
        })

    def test_default_index_1(self, monkeypatch):
        """LLM_API_KEY 未设置时默认指向第 1 个"""
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        result = _resolve_active_provider(self._providers("dashscope", "openai"))
        assert result == "dashscope"

    def test_explicit_index(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "2")
        result = _resolve_active_provider(self._providers("dashscope", "openai", "anthropic"))
        assert result == "openai"

    def test_index_out_of_range(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "99")
        with pytest.raises(ValueError, match="超出范围"):
            _resolve_active_provider(self._providers("dashscope"))

    def test_non_numeric(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        with pytest.raises(ValueError, match="必须是 provider 序号"):
            _resolve_active_provider(self._providers("dashscope"))

    def test_empty_providers(self):
        with pytest.raises(ValueError, match="没有配置任何 LLM provider"):
            _resolve_active_provider(ProvidersConfig(providers={}))
