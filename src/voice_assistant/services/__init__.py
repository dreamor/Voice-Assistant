"""服务模块"""

from voice_assistant.services.router import CommandRouter, simple_classify_intent

__all__ = ['CommandRouter', 'simple_classify_intent']