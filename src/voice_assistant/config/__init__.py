"""
配置管理模块
从 config.yaml 和 .env 加载配置
"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(override=True)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HotwordsConfig:
    """热词配置"""
    enabled: bool
    config_file: str
    vocabulary_id: str | None


@dataclass(frozen=True)
class LocalASRConfig:
    """本地 FunASR 配置"""
    enabled: bool
    model_path: str | None
    device: str
    vad_threshold: float


@dataclass
class ASRConfig:
    """ASR 配置"""
    model: str
    base_url: str
    api_key: str
    language_hints: list
    disfluency_removal_enabled: bool
    max_sentence_silence: int
    hotwords: HotwordsConfig
    use_local: bool
    local: LocalASRConfig


@dataclass
class LLMConfig:
    """LLM 配置（base_url / api_key 由当前 provider 提供；model 默认取 provider.models[0]）"""
    max_tokens: int
    temperature: float
    model: str = ""  # 启动时为空，由 _resolve_default_model 填充


@dataclass(frozen=True)
class TTSConfig:
    """TTS 配置"""
    provider: str = "edge-tts"
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = ""
    pitch: str = ""


@dataclass
class AudioConfig:
    """音频配置"""
    sample_rate: int
    tts: TTSConfig = field(default_factory=TTSConfig)


@dataclass(frozen=True)
class VADConfig:
    """VAD 配置"""
    threshold: float
    silence_timeout: float
    min_speech: float
    wait_timeout: float
    max_recording: float


@dataclass(frozen=True)
class HistoryConfig:
    """对话历史配置"""
    max_turns: int


@dataclass(frozen=True)
class LoggingConfig:
    """日志配置"""
    level: str
    format: str


@dataclass(frozen=True)
class AgentConfig:
    """Agent 配置"""
    max_iterations: int = 5
    confirmation_timeout: int = 60


@dataclass(frozen=True)
class ToolOverrideConfig:
    """单个工具安全级别覆盖"""
    name: str
    level: str


@dataclass(frozen=True)
class ToolsConfig:
    """Tools 配置"""
    blocked: tuple = ()
    overrides: tuple = ()


@dataclass(frozen=True)
class ProviderModelConfig:
    """Provider 下的单个模型配置"""
    id: str
    name: str


@dataclass(frozen=True)
class ProviderConfig:
    """单个 Provider 配置"""
    name: str
    litellm_prefix: str
    base_url: str | None
    api_key_env: str
    models: list[ProviderModelConfig] = field(default_factory=list)
    is_custom: bool = False

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env)

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)


@dataclass
class ProvidersConfig:
    """多 Provider 配置"""
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    def get_provider(self, provider_id: str) -> ProviderConfig | None:
        return self.providers.get(provider_id)

    def get_all_provider_ids(self) -> list[str]:
        return list(self.providers.keys())


@dataclass
class AppConfig:
    """应用配置"""
    name: str
    version: str
    asr: ASRConfig
    llm: LLMConfig
    audio: AudioConfig
    vad: VADConfig
    history: HistoryConfig
    logging: LoggingConfig
    agent: AgentConfig = field(default_factory=AgentConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    providers: ProvidersConfig = field(default_factory=ProvidersConfig)
    provider: str = ""


def _find_project_root() -> Path:
    """查找项目根目录"""
    current = Path(__file__).resolve().parent
    while current.parent != current:
        if (current / "config.yaml").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent


def _load_custom_providers(project_root: Path) -> dict[str, ProviderConfig]:
    """从 config/custom_providers.yaml 加载自定义 Provider"""
    path = project_root / "config" / "custom_providers.yaml"
    if not path.exists():
        return {}

    try:
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"[Config] 加载自定义 Provider 失败: {e}")
        return {}

    providers = {}
    for pid, pdata in data.items():
        models = [
            ProviderModelConfig(id=m['id'], name=m.get('name', m['id']))
            for m in pdata.get('models', [])
        ]
        providers[pid] = ProviderConfig(
            name=pdata.get('name', pid),
            litellm_prefix=pdata.get('litellm_prefix', 'openai'),
            base_url=pdata.get('base_url'),
            api_key_env=pdata.get('api_key_env', f'{pid.upper().replace("-", "_")}_API_KEY'),
            models=models,
            is_custom=True,
        )

    return providers


def save_custom_provider(
    provider_id: str,
    name: str,
    base_url: str,
    api_key_env: str,
    litellm_prefix: str,
    models: list[str],
) -> ProviderConfig:
    """保存自定义 Provider 到 config/custom_providers.yaml 并更新内存配置"""
    project_root = _find_project_root()
    config_dir = project_root / "config"
    config_dir.mkdir(exist_ok=True)
    path = config_dir / "custom_providers.yaml"

    if path.exists():
        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data[provider_id] = {
        'name': name,
        'litellm_prefix': litellm_prefix,
        'base_url': base_url,
        'api_key_env': api_key_env,
        'models': [{'id': m, 'name': m} for m in models],
    }

    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    provider_cfg = ProviderConfig(
        name=name,
        litellm_prefix=litellm_prefix,
        base_url=base_url,
        api_key_env=api_key_env,
        models=[ProviderModelConfig(id=m, name=m) for m in models],
        is_custom=True,
    )
    config.providers.providers[provider_id] = provider_cfg
    logger.info(f"[Config] 保存自定义 Provider: {provider_id} ({name})")
    return provider_cfg


def update_custom_provider(
    provider_id: str,
    *,
    name: str | None = None,
    base_url: str | None = None,
    litellm_prefix: str | None = None,
    models: list[str] | None = None,
) -> ProviderConfig | None:
    """部分更新自定义 Provider。仅传入的字段被更新。

    Returns:
        更新后的 ProviderConfig，若 Provider 不存在或非自定义则返回 None。
    """
    existing = config.providers.get_provider(provider_id)
    if existing is None or not existing.is_custom:
        return None

    new_name = name if name is not None else existing.name
    new_base_url = base_url if base_url is not None else existing.base_url
    new_prefix = litellm_prefix if litellm_prefix is not None else existing.litellm_prefix
    new_models = models if models is not None else [m.id for m in existing.models]

    return save_custom_provider(
        provider_id=provider_id,
        name=new_name,
        base_url=new_base_url or "",
        api_key_env=existing.api_key_env,
        litellm_prefix=new_prefix,
        models=new_models,
    )


def delete_custom_provider(provider_id: str) -> bool:
    """从 config/custom_providers.yaml 删除自定义 Provider"""
    project_root = _find_project_root()
    path = project_root / "config" / "custom_providers.yaml"

    if not path.exists():
        return False

    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    if provider_id not in data:
        return False

    del data[provider_id]

    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    config.providers.providers.pop(provider_id, None)
    logger.info(f"[Config] 删除自定义 Provider: {provider_id}")
    return True


def _validate_config(cfg: AppConfig) -> list[str]:
    """校验配置，返回警告列表（非致命问题）和抛出异常（致命问题）

    Returns:
        warnings: 非致命警告列表
    """
    warnings: list[str] = []

    # ASR Key 必填（除非走本地模式）
    if not cfg.asr.api_key and not cfg.asr.use_local:
        raise ValueError("ASR_API_KEY 环境变量未设置（或设置 asr.use_local: true）")

    # provider 由 _resolve_active_provider 在加载阶段确定，这里只校验 key
    current_provider = cfg.providers.providers[cfg.provider]
    if not current_provider.api_key:
        raise ValueError(
            f"Provider {current_provider.name} 未配置 API Key，"
            f"请在 .env 设置环境变量 {current_provider.api_key_env}"
        )

    # 范围校验
    if not 0 <= cfg.llm.temperature <= 2:
        warnings.append(f"llm.temperature={cfg.llm.temperature} 超出推荐范围 [0, 2]")
    if cfg.llm.max_tokens < 1:
        raise ValueError(f"llm.max_tokens={cfg.llm.max_tokens} 必须 >= 1")
    if cfg.vad.threshold < 0 or cfg.vad.threshold > 1:
        warnings.append(f"vad.threshold={cfg.vad.threshold} 超出范围 [0, 1]")
    if cfg.audio.sample_rate not in (8000, 16000, 22050, 44100, 48000):
        warnings.append(f"audio.sample_rate={cfg.audio.sample_rate} 非标准采样率")
    if cfg.agent.max_iterations < 1:
        raise ValueError(f"agent.max_iterations={cfg.agent.max_iterations} 必须 >= 1")
    if cfg.history.max_turns < 1:
        raise ValueError(f"history.max_turns={cfg.history.max_turns} 必须 >= 1")

    # TTS 配置校验
    if cfg.audio.tts.provider not in ("edge-tts",):
        warnings.append(f"tts.provider={cfg.audio.tts.provider} 不是已知 provider，可能无法工作")

    return warnings


def _merge_providers(built_in: ProvidersConfig, custom: dict[str, ProviderConfig]) -> ProvidersConfig:
    """合并内置 Provider 和自定义 Provider"""
    merged = dict(built_in.providers)
    merged.update(custom)
    return ProvidersConfig(providers=merged)


def _load_providers_config(cfg: dict) -> ProvidersConfig:
    """从 YAML 配置加载多 Provider 配置"""
    providers_raw = cfg.get('providers', {})
    if not providers_raw:
        return ProvidersConfig()

    providers = {}
    for pid, pdata in providers_raw.items():
        models = [
            ProviderModelConfig(id=m['id'], name=m.get('name', m['id']))
            for m in pdata.get('models', [])
        ]
        providers[pid] = ProviderConfig(
            name=pdata.get('name', pid),
            litellm_prefix=pdata.get('litellm_prefix', 'openai'),
            base_url=pdata.get('base_url'),
            api_key_env=pdata.get('api_key_env', f'{pid.upper()}_API_KEY'),
            models=models,
        )

    return ProvidersConfig(providers=providers)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """从 YAML 和环境变量加载配置"""
    project_root = _find_project_root()
    full_path = project_root / config_path

    with open(full_path, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    # 加载并合并 providers（内置 + 自定义）
    custom_providers = _load_custom_providers(project_root)
    merged_providers = _merge_providers(_load_providers_config(cfg), custom_providers)

    app_config = AppConfig(
        name=cfg['app']['name'],
        version=cfg['app']['version'],
        asr=ASRConfig(
            model=cfg['asr']['model'],
            base_url=cfg['asr']['base_url'],
            api_key=os.getenv('ASR_API_KEY'),
            language_hints=cfg['asr'].get('language_hints', ['zh', 'en']),
            disfluency_removal_enabled=cfg['asr'].get('disfluency_removal_enabled', False),
            max_sentence_silence=cfg['asr'].get('max_sentence_silence', 800),
            hotwords=HotwordsConfig(
                enabled=cfg['asr'].get('hotwords', {}).get('enabled', False),
                config_file=cfg['asr'].get('hotwords', {}).get('config_file', 'config/hotwords.json'),
                vocabulary_id=cfg['asr'].get('hotwords', {}).get('vocabulary_id'),
            ),
            use_local=cfg['asr'].get('use_local', False),
            local=LocalASRConfig(
                enabled=cfg['asr'].get('local', {}).get('enabled', False),
                model_path=cfg['asr'].get('local', {}).get('model_path'),
                device=cfg['asr'].get('local', {}).get('device', 'cpu'),
                vad_threshold=cfg['asr'].get('local', {}).get('vad_threshold', 0.5),
            ),
        ),
        llm=LLMConfig(
            max_tokens=cfg['llm']['max_tokens'],
            temperature=cfg['llm']['temperature'],
        ),
        audio=AudioConfig(
            sample_rate=cfg['audio']['sample_rate'],
            tts=TTSConfig(
                provider=cfg.get('tts', {}).get('provider', 'edge-tts'),
                voice=cfg.get('tts', {}).get('voice', 'zh-CN-XiaoxiaoNeural'),
                rate=cfg.get('tts', {}).get('rate', ''),
                pitch=cfg.get('tts', {}).get('pitch', ''),
            ),
        ),
        vad=VADConfig(
            threshold=cfg['vad']['threshold'],
            silence_timeout=cfg['vad']['silence_timeout'],
            min_speech=cfg['vad']['min_speech'],
            wait_timeout=cfg['vad']['wait_timeout'],
            max_recording=cfg['vad']['max_recording'],
        ),
        history=HistoryConfig(max_turns=cfg['history']['max_turns']),
        logging=LoggingConfig(
            level=cfg['logging']['level'],
            format=cfg['logging']['format'],
        ),
        agent=AgentConfig(
            max_iterations=cfg.get('agent', {}).get('max_iterations', 5),
            confirmation_timeout=cfg.get('agent', {}).get('confirmation_timeout', 60),
        ),
        tools=ToolsConfig(
            blocked=tuple(cfg.get('tools', {}).get('blocked', [])),
            overrides=tuple(
                ToolOverrideConfig(name=o['name'], level=o['level'])
                for o in cfg.get('tools', {}).get('overrides', [])
            ),
        ),
        providers=merged_providers,
        provider=_resolve_active_provider(merged_providers),
    )

    # 主模型默认取当前 provider 的第一个 model（用户可在 ⚙ 切换覆盖）
    active_provider = app_config.providers.providers[app_config.provider]
    if active_provider.models:
        app_config.llm.model = active_provider.models[0].id

    # 配置校验
    validation_warnings = _validate_config(app_config)
    for w in validation_warnings:
        logger.warning(f"[Config] {w}")

    return app_config


def _resolve_active_provider(providers: ProvidersConfig) -> str:
    """根据 .env 中 LLM_API_KEY 序号解析当前活跃 provider ID。

    LLM_API_KEY 是一个数字（默认 1），指向 providers 列表中第 N 个。
    内置 provider 按 config.yaml 中出现顺序排号；自定义 provider 紧随其后。

    Returns:
        provider ID 字符串

    Raises:
        ValueError: LLM_API_KEY 非数字、超出范围、或 providers 为空
    """
    provider_ids = list(providers.providers.keys())
    if not provider_ids:
        raise ValueError("config.yaml 没有配置任何 LLM provider")

    raw = os.getenv('LLM_API_KEY', '1').strip()
    try:
        idx = int(raw)
    except ValueError as e:
        raise ValueError(
            f"LLM_API_KEY 必须是 provider 序号（数字 1-{len(provider_ids)}），实际收到: {raw!r}"
        ) from e

    if idx < 1 or idx > len(provider_ids):
        raise ValueError(
            f"LLM_API_KEY={idx} 超出范围 [1, {len(provider_ids)}]。"
            f"当前 provider 列表: {[(i+1, pid) for i, pid in enumerate(provider_ids)]}"
        )

    return provider_ids[idx - 1]


# 全局配置实例
try:
    config = load_config()
except Exception as e:
    logger.error(f"配置加载失败：{e}")
    raise RuntimeError(f"配置加载失败，请检查 config.yaml 和 .env 文件: {e}") from e


__all__ = ['config', 'load_config', 'AppConfig', 'AgentConfig', 'ToolsConfig', 'TTSConfig', 'save_custom_provider', 'delete_custom_provider']
