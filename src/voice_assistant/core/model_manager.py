"""
模型管理器模块
支持获取阿里云可用模型列表、模型切换和故障转移

功能：
- 获取阿里云百炼平台所有可用模型
- 构建模型候选队列
- 错误判断，决定是否切换模型
- 运行时自动切换模型
"""
import logging
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

# 备用模型优先选用的关键词（按优先级排序）
FALLBACK_MODEL_PREFERENCES = ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-long", "qwen"]


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    base_url: str
    api_key: str

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

    def next_model(self) -> Optional[ModelConfig]:
        """切换到下一个模型"""
        if self.current_index < len(self.models) - 1:
            self.current_index += 1
            logger.warning(f"[ModelManager] 切换到备用模型: {self.current().name}")
            return self.current()
        return None

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
        self._cached_models: Optional[list[dict]] = None

    def list_available_models(self, api_key: Optional[str] = None) -> list[dict]:
        """
        获取阿里云百炼平台所有可用模型

        Args:
            api_key: API Key，默认从配置读取

        Returns:
            模型列表，每项包含 id、object、created、owned_by 字段
        """
        api_key = api_key or config.llm.api_key
        if not api_key:
            logger.warning("[ModelManager] 未配置 API Key")
            return []

        base_url = config.llm.base_url
        if base_url.endswith('/v1'):
            base_url = base_url[:-3]
        url = f"{base_url}/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            models = response.json().get("data", [])
            self._cached_models = models
            logger.info(f"[ModelManager] 获取到 {len(models)} 个可用模型")
            return models
        except requests.HTTPError as e:
            logger.error(f"[ModelManager] 获取模型列表失败 (HTTP {e.response.status_code}): {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"[ModelManager] 获取模型列表异常: {e}")
            return []

    def search_models(self, keyword: str, api_key: Optional[str] = None) -> list[str]:
        """
        按关键词搜索模型

        Args:
            keyword: 过滤关键词，大小写不敏感
            api_key: API Key

        Returns:
            匹配的模型名称列表
        """
        all_models = self._cached_models or self.list_available_models(api_key)
        keyword_lower = keyword.lower()
        return sorted(
            model["id"] for model in all_models
            if keyword_lower in model["id"].lower()
        )

    def build_model_queue(self, api_key: Optional[str] = None) -> ModelQueue:
        """
        构建模型候选队列

        队列顺序：
        1. 主模型（配置文件中的模型）
        2. 从百炼平台获取的备用模型

        Args:
            api_key: API Key

        Returns:
            模型队列
        """
        api_key = api_key or config.llm.api_key
        base_url = config.llm.base_url
        primary_model = config.llm.model

        queue: list[ModelConfig] = []

        # 添加主模型
        if primary_model and api_key:
            queue.append(ModelConfig(
                name=primary_model,
                base_url=base_url,
                api_key=api_key
            ))
            logger.info(f"[ModelManager] 主模型: {primary_model}")

        # 获取备用模型
        try:
            all_models = self.list_available_models(api_key)
            model_ids = [m["id"] for m in all_models]

            added_fallbacks: set[str] = set()
            for preference in FALLBACK_MODEL_PREFERENCES:
                for model_id in model_ids:
                    if (
                        preference in model_id
                        and model_id not in added_fallbacks
                        and model_id != primary_model
                    ):
                        queue.append(ModelConfig(
                            name=model_id,
                            base_url=base_url,
                            api_key=api_key
                        ))
                        added_fallbacks.add(model_id)
                        logger.info(f"[ModelManager] 备用模型: {model_id}")
                        break  # 每个偏好只添加一个
        except Exception as e:
            logger.warning(f"[ModelManager] 获取备用模型失败: {e}")

        self._queue = ModelQueue(models=queue)
        return self._queue

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

        # 检查 HTTP 状态码
        if isinstance(error, requests.HTTPError):
            status_code = getattr(error.response, 'status_code', None)
            if status_code:
                # 400 可能是输入问题，需要检查错误消息
                if status_code == 400:
                    # 已在上面检查了错误消息
                    return True
                # 401/403: 认证失败 → 切换
                # 402: 余额不足 → 切换
                # 404: 模型不存在 → 切换
                # 429/500/502/503: 限流或服务不可用 → 切换
                return status_code >= 401

        # 网络错误、超时等 → 切换
        return True

    def switch_to_next_model(self) -> Optional[ModelConfig]:
        """
        切换到下一个备用模型

        Returns:
            切换后的模型配置，如果没有可用模型返回 None
        """
        if self._queue is None:
            logger.warning("[ModelManager] 模型队列未初始化")
            return None

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
        """重置到主模型"""
        if self._queue:
            self._queue.reset()
            logger.info("[ModelManager] 已重置到主模型")


# 全局模型管理器实例
model_manager = ModelManager()