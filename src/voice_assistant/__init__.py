"""
Voice Assistant - 中文语音助手

一个端到端的中文语音交互系统，支持本地/在线 LLM 切换。
"""

__version__ = "2.0.0"
__author__ = "Voice Assistant Team"

# 导出公共 API
from voice_assistant.config import AppConfig, config, load_config

__all__ = [
    'config',
    'load_config',
    'AppConfig',
    '__version__',
]
