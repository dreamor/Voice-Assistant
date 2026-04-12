"""
配置管理模块
从 config.yaml 和 .env 加载配置
"""
import logging
import os
from dataclasses import dataclass
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


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class LLMConfig:
    """LLM 配置"""
    model: str
    base_url: str
    api_key: str
    max_tokens: int
    temperature: float


@dataclass(frozen=True)
class AudioConfig:
    """音频配置"""
    sample_rate: int
    edge_tts_voice: str


@dataclass(frozen=True)
class VADConfig:
    """VAD 配置"""
    threshold: float
    silence_timeout: float
    min_speech: float
    wait_timeout: float
    max_recording: float


@dataclass(frozen=True)
class InterpreterConfig:
    """Open Interpreter 配置"""
    auto_run: bool
    verbose: bool


@dataclass(frozen=True)
class HistoryConfig:
    """对话历史配置"""
    max_turns: int


@dataclass(frozen=True)
class IntentConfig:
    """意图识别配置"""
    model: str
    timeout: int


@dataclass(frozen=True)
class LoggingConfig:
    """日志配置"""
    level: str
    format: str


@dataclass(frozen=True)
class AppConfig:
    """应用配置"""
    name: str
    version: str
    asr: ASRConfig
    llm: LLMConfig
    audio: AudioConfig
    vad: VADConfig
    interpreter: InterpreterConfig
    history: HistoryConfig
    intent: IntentConfig
    logging: LoggingConfig


def _find_project_root() -> Path:
    """查找项目根目录"""
    # 从当前文件所在目录向上查找，直到找到 config.yaml
    current = Path(__file__).resolve().parent
    while current.parent != current:
        if (current / "config.yaml").exists():
            return current
        current = current.parent
    # 如果找不到，返回 src 的父目录
    return Path(__file__).resolve().parent.parent.parent


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """从 YAML 和环境变量加载配置"""
    project_root = _find_project_root()
    full_path = project_root / config_path

    with open(full_path, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    return AppConfig(
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
            model=cfg['llm']['model'],
            base_url=cfg['llm']['base_url'],
            api_key=os.getenv('LLM_API_KEY'),
            max_tokens=cfg['llm']['max_tokens'],
            temperature=cfg['llm']['temperature'],
        ),
        audio=AudioConfig(
            sample_rate=cfg['audio']['sample_rate'],
            edge_tts_voice=cfg['audio']['edge_tts_voice'],
        ),
        vad=VADConfig(
            threshold=cfg['vad']['threshold'],
            silence_timeout=cfg['vad']['silence_timeout'],
            min_speech=cfg['vad']['min_speech'],
            wait_timeout=cfg['vad']['wait_timeout'],
            max_recording=cfg['vad']['max_recording'],
        ),
        interpreter=InterpreterConfig(
            auto_run=cfg['interpreter']['auto_run'],
            verbose=cfg['interpreter']['verbose'],
        ),
        history=HistoryConfig(max_turns=cfg['history']['max_turns']),
        intent=IntentConfig(
            model=cfg.get('intent', {}).get('model', 'qwen-turbo'),
            timeout=cfg.get('intent', {}).get('timeout', 5),
        ),
        logging=LoggingConfig(
            level=cfg['logging']['level'],
            format=cfg['logging']['format'],
        ),
    )


# 全局配置实例
try:
    config = load_config()
except Exception as e:
    logger.error(f"配置加载失败：{e}")
    raise RuntimeError(f"配置加载失败，请检查 config.yaml 和 .env 文件: {e}") from e


__all__ = ['config', 'load_config', 'AppConfig']
