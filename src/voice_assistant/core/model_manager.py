"""
模型管理器模块
从配置文件读取备选模型列表，支持模型切换和故障转移

功能：
- 从配置文件读取备选模型列表
- 构建模型候选队列
- 错误判断，决定是否切换模型
- 运行时自动切换模型
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from voice_assistant.config import config

logger = logging.getLogger(__name__)

# 不应切换模型的错误消息关键词（属于输入问题，换模型也无法解决）
# 来源：https://www.alibabacloud.com/help/zh/model-studio/error-code
NON_SWITCHABLE_ERROR_MESSAGES = [
    "Range of input length should be",   # 输入内容超过模型上下文长度限制
    "Range of max_tokens should be",      # max_tokens 参数超出范围
    "Temperature should be in",           # temperature 参数错误
    "Range of top_p should be",           # top_p 参数错误
    "content_filter",                     # 内容违规
    "[] is too short",                    # messages 为空
    "Either \"prompt\" or \"messages\" must exist",  # 缺少必要参数
    "'messages' must contain the word 'json'",       # 结构化输出格式错误
    "messages with role \"tool\" must be a response",  # 工具调用格式错误
    "Input should be a valid dictionary",  # messages 格式错误
]


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    base_url: str
    api_key: str
    litellm_prefix: str = "openai"

    @property
    def litellm_model(self) -> str:
        """返回 litellm 格式的模型名（prefix/model）"""
        return f"{self.litellm_prefix}/{self.name}"

    def __str__(self) -> str:
        return f"ModelConfig(name={self.name}, base_url={self.base_url})"


@dataclass
class ModelQueue:
    """模型队列管理"""
    models: list[ModelConfig] = field(default_factory=list)
    current_index: int = 0

    def current(self) -> Optional[ModelConfig]:
        """获取当前模型"""
        if 0 <= self.current_index < len(self.models):
            return self.models[self.current_index]
        return None

    def advance(self) -> None:
        """前进到下一个模型（不返回）"""
        if self.current_index < len(self.models) - 1:
            self.current_index += 1

    def next_model(self) -> Optional[ModelConfig]:
        """前进并返回下一个模型，如果没有更多模型返回 None"""
        if self.current_index >= len(self.models) - 1:
            return None
        self.advance()
        return self.current()

    def reset(self) -> None:
        """重置到第一个模型"""
        self.current_index = 0

    def has_fallback(self) -> bool:
        """是否还有备用模型"""
        return self.current_index < len(self.models) - 1


class ModelManager:
    """模型管理器"""

    def __init__(self):
        self._queue: Optional[ModelQueue] = None
        self._last_fail_time: dict[str, float] = {}  # model_name -> timestamp
        self._cooldown_seconds: float = 60.0  # 冷却时间：失败后60秒内不重试该模型

    def build_model_queue(self, api_key: Optional[str] = None) -> ModelQueue:
        """
        构建模型候选队列

        优先使用 providers 配置构建；如果无 providers 配置，
        回退到传统的单一 base_url + llm_models.yaml 模式。

        Args:
            api_key: API Key，默认从配置读取

        Returns:
            模型队列
        """
        provider_id = config.provider
        providers_cfg = config.providers

        # Provider 模式：从 providers 配置构建
        if provider_id and providers_cfg.providers:
            provider = providers_cfg.get_provider(provider_id)
            if provider and provider.api_key:
                return self._build_from_provider(provider)

        # 回退模式：传统单一 base_url
        return self._build_from_legacy(api_key)

    def _build_from_provider(self, provider) -> ModelQueue:
        """从 Provider 配置构建模型队列"""
        queue: list[ModelConfig] = []
        added_models: set[str] = set()
        api_key = provider.api_key
        base_url = provider.base_url or ""
        prefix = provider.litellm_prefix

        for model_cfg in provider.models:
            if model_cfg.id not in added_models:
                queue.append(ModelConfig(
                    name=model_cfg.id,
                    base_url=base_url,
                    api_key=api_key,
                    litellm_prefix=prefix,
                ))
                added_models.add(model_cfg.id)
                logger.info(f"[ModelManager] Provider {provider.name} 模型: {model_cfg.id}")

        if not queue:
            logger.warning(f"[ModelManager] Provider {provider.name} 没有可用模型")

        self._queue = ModelQueue(models=queue)
        return self._queue

    def _build_from_legacy(self, api_key: Optional[str] = None) -> ModelQueue:
        """从传统配置构建模型队列（向后兼容）"""
        api_key = api_key or config.llm.api_key
        base_url = config.llm.base_url
        primary_model = config.llm.model

        queue: list[ModelConfig] = []
        added_models: set[str] = set()

        if primary_model and api_key:
            queue.append(ModelConfig(
                name=primary_model,
                base_url=base_url,
                api_key=api_key,
            ))
            added_models.add(primary_model)
            logger.info(f"[ModelManager] 主模型: {primary_model}")

        for model_cfg in config.llm_models.models:
            if model_cfg.name not in added_models and api_key:
                queue.append(ModelConfig(
                    name=model_cfg.name,
                    base_url=base_url,
                    api_key=api_key,
                ))
                added_models.add(model_cfg.name)
                logger.info(f"[ModelManager] 备用模型: {model_cfg.name}")

        if not queue:
            logger.warning("[ModelManager] 没有可用的模型")

        self._queue = ModelQueue(models=queue)
        return self._queue

    def switch_provider(self, provider_id: str, model_id: Optional[str] = None) -> Optional[ModelConfig]:
        """切换到指定 Provider

        Args:
            provider_id: Provider ID
            model_id: 可选的模型 ID，默认使用该 Provider 的第一个模型

        Returns:
            切换后的模型配置
        """
        provider = config.providers.get_provider(provider_id)
        if not provider:
            logger.error(f"[ModelManager] 未知的 Provider: {provider_id}")
            return None

        if not provider.api_key:
            logger.error(f"[ModelManager] Provider {provider.name} 未配置 API Key ({provider.api_key_env})")
            return None

        queue = self._build_from_provider(provider)
        if model_id:
            for i, m in enumerate(queue.models):
                if m.name == model_id:
                    queue.current_index = i
                    break

        # 同步更新 config.llm
        config.llm.model = queue.current().name if queue.current() else config.llm.model
        config.llm.base_url = queue.current().base_url if queue.current() else config.llm.base_url
        config.llm.api_key = queue.current().api_key if queue.current() else config.llm.api_key
        config.provider = provider_id

        logger.info(f"[ModelManager] 切换到 Provider: {provider.name}, 模型: {queue.current().name if queue.current() else 'N/A'}")
        return queue.current()

    def get_queue(self) -> Optional[ModelQueue]:
        """获取当前模型队列"""
        return self._queue

    def should_switch_model(self, error: Exception) -> bool:
        """
        判断当前错误是否应该切换模型

        基于阿里云百炼官方错误文档：
        - 模型不存在、余额不足、认证失败、服务不可用 → 切换
        - 上下文超长、参数格式错误、内容违规等输入问题 → 不切换

        Args:
            error: 发生的异常

        Returns:
            是否应该切换模型
        """
        error_str = str(error).lower()

        # 检查是否是输入问题
        for keyword in NON_SWITCHABLE_ERROR_MESSAGES:
            if keyword.lower() in error_str:
                logger.info(f"[ModelManager] 输入问题，不切换模型: {keyword}")
                return False

        # 检查 HTTP 状态码（支持 litellm.APIError 和 requests.HTTPError）
        status_code = getattr(error, 'status_code', None)
        if status_code is None and isinstance(error, requests.HTTPError):
            status_code = getattr(error.response, 'status_code', None)

        if status_code:
            if status_code == 400:
                logger.info(f"[ModelManager] HTTP 400 错误，不切换模型（通常是请求格式问题）")
                return False
            return status_code >= 401

        # 网络错误、超时等 → 切换
        return True

    def record_failure(self, model_name: str) -> None:
        """记录模型失败时间"""
        self._last_fail_time[model_name] = time.time()
        logger.debug(f"[ModelManager] 记录模型失败: {model_name}")

    def switch_to_next_model(self) -> Optional[ModelConfig]:
        """切换到下一个备用模型"""
        if self._queue is None:
            logger.warning("[ModelManager] 模型队列未初始化")
            return None

        current = self._queue.current()
        if current:
            self.record_failure(current.name)

        return self._queue.next_model()

    def get_current_model(self) -> Optional[ModelConfig]:
        """
        获取当前模型配置

        Returns:
            当前模型配置
        """
        if self._queue is None:
            return None
        return self._queue.current()

    def reset_to_primary(self) -> None:
        """重置到主模型（除非主模型在冷却期内）"""
        if self._queue:
            primary = self._queue.models[0] if self._queue.models else None
            if primary:
                last_fail = self._last_fail_time.get(primary.name, 0)
                if time.time() - last_fail < self._cooldown_seconds:
                    logger.info(f"[ModelManager] 主模型 {primary.name} 仍在冷却期内，保持当前模型")
                    return
            self._queue.reset()
            logger.info("[ModelManager] 已重置到主模型")


# 全局模型管理器实例
model_manager = ModelManager()