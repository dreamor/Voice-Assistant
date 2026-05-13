"""模型管理器测试"""
import sys
from unittest.mock import MagicMock

from voice_assistant.core.model_manager import (
    NON_SWITCHABLE_ERROR_MESSAGES,
    ModelConfig,
    ModelManager,
    ModelQueue,
)


class TestModelConfig:
    """测试 ModelConfig 数据类"""

    def test_model_config_creation(self):
        """测试创建模型配置"""
        config = ModelConfig(
            name="qwen-plus",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="test-key"
        )
        assert config.name == "qwen-plus"
        assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert config.api_key == "test-key"

    def test_model_config_str(self):
        """测试字符串表示"""
        config = ModelConfig(
            name="qwen-plus",
            base_url="https://example.com/v1",
            api_key="secret"
        )
        assert "qwen-plus" in str(config)
        assert "example.com" in str(config)
        assert "secret" not in str(config)  # 不应暴露 API key


class TestModelQueue:
    """测试 ModelQueue 队列管理"""

    def test_empty_queue(self):
        """测试空队列"""
        queue = ModelQueue(models=[])
        assert queue.current() is None
        assert queue.has_fallback() is False
        assert queue.next_model() is None

    def test_single_model_queue(self):
        """测试单模型队列"""
        model = ModelConfig(name="model-1", base_url="url", api_key="key")
        queue = ModelQueue(models=[model])

        assert queue.current() == model
        assert queue.has_fallback() is False
        assert queue.next_model() is None

    def test_multi_model_queue(self):
        """测试多模型队列"""
        models = [
            ModelConfig(name="model-1", base_url="url", api_key="key"),
            ModelConfig(name="model-2", base_url="url", api_key="key"),
            ModelConfig(name="model-3", base_url="url", api_key="key"),
        ]
        queue = ModelQueue(models=models)

        # 初始指向第一个
        assert queue.current_index == 0
        assert queue.current().name == "model-1"
        assert queue.has_fallback() is True

        # 切换到下一个
        next_model = queue.next_model()
        assert next_model.name == "model-2"
        assert queue.current_index == 1
        assert queue.has_fallback() is True

        # 再切换
        next_model = queue.next_model()
        assert next_model.name == "model-3"
        assert queue.current_index == 2
        assert queue.has_fallback() is False

        # 没有更多备用模型
        assert queue.next_model() is None

    def test_queue_reset(self):
        """测试重置队列"""
        models = [
            ModelConfig(name="model-1", base_url="url", api_key="key"),
            ModelConfig(name="model-2", base_url="url", api_key="key"),
        ]
        queue = ModelQueue(models=models)

        queue.next_model()
        assert queue.current_index == 1

        queue.reset()
        assert queue.current_index == 0
        assert queue.current().name == "model-1"


class TestModelManager:
    """测试 ModelManager"""

    def test_should_switch_model_non_switchable_errors(self):
        """测试不应切换模型的错误"""
        manager = ModelManager()

        # 模拟输入问题的错误
        for keyword in NON_SWITCHABLE_ERROR_MESSAGES:
            error = Exception(f"Error: {keyword} occurred")
            assert manager.should_switch_model(error) is False, f"Should not switch for: {keyword}"

    def test_should_switch_model_switchable_errors(self):
        """测试应该切换模型的错误"""
        manager = ModelManager()

        # 网络错误
        error = ConnectionError("Network error")
        assert manager.should_switch_model(error) is True

        # 超时错误
        error = TimeoutError("Request timeout")
        assert manager.should_switch_model(error) is True

        # HTTP 500 错误
        error = Exception("HTTP 500")
        assert manager.should_switch_model(error) is True

    def test_should_switch_model_with_status_code(self):
        """测试带 status_code 属性的错误（litellm 格式）"""
        manager = ModelManager()

        # litellm APIError 带 status_code=500 → 切换
        error = MagicMock()
        error.status_code = 500
        error.__str__ = lambda self: "Internal Server Error"
        assert manager.should_switch_model(error) is True

        # status_code=400 且无输入问题关键词 → 不切换
        error = MagicMock()
        error.status_code = 400
        error.__str__ = lambda self: "Bad request"
        assert manager.should_switch_model(error) is False

        # status_code=401 → 切换
        error = MagicMock()
        error.status_code = 401
        error.__str__ = lambda self: "Unauthorized"
        assert manager.should_switch_model(error) is True

    def test_should_switch_model_http_400_input_error(self):
        """测试 HTTP 400 输入错误"""
        manager = ModelManager()

        # 400 且包含输入问题关键词 - 不切换
        error_msg = "Range of input length should be less than 4000"
        error = Exception(error_msg)
        assert manager.should_switch_model(error) is False

    def test_should_switch_model_http_400_other_error(self):
        """测试 HTTP 400 其他错误"""
        manager = ModelManager()

        # 400 但不是输入问题 - 切换
        error = Exception("Bad request: model not found")
        assert manager.should_switch_model(error) is True

    def test_build_model_queue_from_provider(self):
        """主模型存在于 provider.models 时，应被提到队首；其余按定义顺序作为 fallback"""
        from voice_assistant.config import ProviderConfig, ProviderModelConfig, ProvidersConfig
        mm_module = sys.modules['voice_assistant.core.model_manager']

        provider = ProviderConfig(
            name="DashScope",
            litellm_prefix="openai",
            base_url="https://example.com/v1",
            api_key_env="LLM_API_KEY",
            models=[
                ProviderModelConfig(id="qwen-plus", name="Qwen Plus"),
                ProviderModelConfig(id="qwen-max", name="Qwen Max"),
                ProviderModelConfig(id="qwen-turbo", name="Qwen Turbo"),
            ],
        )

        mock_config = MagicMock()
        mock_config.provider = "dashscope"
        mock_config.providers = ProvidersConfig(providers={"dashscope": provider})
        mock_config.llm.model = "qwen-max"  # 主模型不是 provider.models[0]

        original = mm_module.config
        mm_module.config = mock_config
        try:
            import os
            os.environ['LLM_API_KEY'] = 'test-key'
            manager = ModelManager()
            queue = manager.build_model_queue()

            # 队首应为主模型 qwen-max；其余按 provider.models 顺序
            assert [m.name for m in queue.models] == ["qwen-max", "qwen-plus", "qwen-turbo"]
            assert queue.current_index == 0
        finally:
            mm_module.config = original

    def test_build_model_queue_primary_not_in_provider(self):
        """主模型不在 provider.models 时，按 provider.models 原序，不强行加入"""
        from voice_assistant.config import ProviderConfig, ProviderModelConfig, ProvidersConfig
        mm_module = sys.modules['voice_assistant.core.model_manager']

        provider = ProviderConfig(
            name="DashScope",
            litellm_prefix="openai",
            base_url="https://example.com/v1",
            api_key_env="LLM_API_KEY",
            models=[
                ProviderModelConfig(id="qwen-plus", name="Qwen Plus"),
                ProviderModelConfig(id="qwen-turbo", name="Qwen Turbo"),
            ],
        )

        mock_config = MagicMock()
        mock_config.provider = "dashscope"
        mock_config.providers = ProvidersConfig(providers={"dashscope": provider})
        mock_config.llm.model = "non-existent-model"

        original = mm_module.config
        mm_module.config = mock_config
        try:
            import os
            os.environ['LLM_API_KEY'] = 'test-key'
            manager = ModelManager()
            queue = manager.build_model_queue()

            assert [m.name for m in queue.models] == ["qwen-plus", "qwen-turbo"]
        finally:
            mm_module.config = original

    def test_build_model_queue_no_provider_raises(self):
        """未配置 provider 时启动应直接抛错"""
        import pytest

        from voice_assistant.config import ProvidersConfig
        mm_module = sys.modules['voice_assistant.core.model_manager']

        mock_config = MagicMock()
        mock_config.provider = ""
        mock_config.providers = ProvidersConfig(providers={})

        original = mm_module.config
        mm_module.config = mock_config
        try:
            manager = ModelManager()
            with pytest.raises(ValueError, match="未配置 LLM provider"):
                manager.build_model_queue()
        finally:
            mm_module.config = original

    def test_record_failure_and_cooldown(self):
        """测试记录失败和冷却机制"""
        manager = ModelManager()
        manager._cooldown_seconds = 0.1  # 短冷却时间用于测试

        # 记录失败
        manager.record_failure("model-1")
        assert "model-1" in manager._last_fail_time

        # 冷却期内
        import time
        time.sleep(0.05)
        assert time.time() - manager._last_fail_time["model-1"] < manager._cooldown_seconds

        # 冷却期后
        time.sleep(0.1)
        assert time.time() - manager._last_fail_time["model-1"] >= manager._cooldown_seconds


class TestConstants:
    """测试常量定义"""

    def test_non_switchable_error_messages_not_empty(self):
        """测试非切换错误消息列表不为空"""
        assert len(NON_SWITCHABLE_ERROR_MESSAGES) > 0

    def test_non_switchable_error_messages_content(self):
        """测试非切换错误消息包含关键内容"""
        # 上下文长度限制
        assert any("input length" in msg for msg in NON_SWITCHABLE_ERROR_MESSAGES)
        # 参数错误
        assert any("max_tokens" in msg for msg in NON_SWITCHABLE_ERROR_MESSAGES)
        # 内容违规
        assert any("content_filter" in msg for msg in NON_SWITCHABLE_ERROR_MESSAGES)
