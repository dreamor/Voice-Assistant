"""模型管理器测试"""
import pytest
from unittest.mock import patch, MagicMock

from voice_assistant.core.model_manager import (
    ModelConfig,
    ModelQueue,
    ModelManager,
    NON_SWITCHABLE_ERROR_MESSAGES,
    FALLBACK_MODEL_PREFERENCES,
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
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        error = Exception("HTTP 500")
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

    @patch('voice_assistant.core.model_manager.requests.get')
    @patch('voice_assistant.core.model_manager.config')
    def test_list_available_models_success(self, mock_config, mock_get):
        """测试成功获取模型列表"""
        mock_config.llm.api_key = "test-key"
        mock_config.llm.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "qwen-plus", "object": "model", "owned_by": "alibaba"},
                {"id": "qwen-turbo", "object": "model", "owned_by": "alibaba"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        manager = ModelManager()
        models = manager.list_available_models()

        assert len(models) == 2
        assert models[0]["id"] == "qwen-plus"
        assert models[1]["id"] == "qwen-turbo"

    @patch('voice_assistant.core.model_manager.requests.get')
    @patch('voice_assistant.core.model_manager.config')
    def test_list_available_models_error(self, mock_config, mock_get):
        """测试获取模型列表失败"""
        mock_config.llm.api_key = "test-key"
        mock_config.llm.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        mock_get.side_effect = Exception("Network error")

        manager = ModelManager()
        models = manager.list_available_models()

        assert models == []

    @patch('voice_assistant.core.model_manager.requests.get')
    @patch('voice_assistant.core.model_manager.config')
    def test_build_model_queue(self, mock_config, mock_get):
        """测试构建模型队列"""
        mock_config.llm.api_key = "test-key"
        mock_config.llm.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_config.llm.model = "qwen-max"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "qwen-max", "object": "model"},
                {"id": "qwen-plus-latest", "object": "model"},
                {"id": "qwen-turbo-latest", "object": "model"},
                {"id": "other-model", "object": "model"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        manager = ModelManager()
        queue = manager.build_model_queue()

        # 主模型 + 两个备用模型
        assert len(queue.models) >= 1
        assert queue.models[0].name == "qwen-max"
        assert queue.current_index == 0

    @patch('voice_assistant.core.model_manager.config')
    def test_build_model_queue_no_api_key(self, mock_config):
        """测试无 API Key 时构建队列"""
        mock_config.llm.api_key = None
        mock_config.llm.base_url = "https://example.com/v1"
        mock_config.llm.model = "test-model"

        manager = ModelManager()
        queue = manager.build_model_queue()

        assert len(queue.models) == 0

    def test_search_models(self):
        """测试搜索模型"""
        manager = ModelManager()
        manager._cached_models = [
            {"id": "qwen-plus-latest"},
            {"id": "qwen-turbo"},
            {"id": "qwen-max"},
            {"id": "other-model"},
        ]

        results = manager.search_models("qwen")
        assert len(results) == 3
        assert "qwen-max" in results
        assert "qwen-plus-latest" in results
        assert "qwen-turbo" in results
        assert "other-model" not in results

    def test_search_models_empty_cache(self):
        """测试空缓存时搜索"""
        manager = ModelManager()
        manager._cached_models = None

        # 没有缓存且无法获取时返回空
        with patch.object(manager, 'list_available_models', return_value=[]):
            results = manager.search_models("qwen")
            assert results == []


class TestConstants:
    """测试常量定义"""

    def test_non_switchable_error_messages_not_empty(self):
        """测试非切换错误消息列表不为空"""
        assert len(NON_SWITCHABLE_ERROR_MESSAGES) > 0

    def test_fallback_model_preferences_order(self):
        """测试备用模型优先级顺序"""
        assert "qwen-plus" in FALLBACK_MODEL_PREFERENCES
        assert "qwen-turbo" in FALLBACK_MODEL_PREFERENCES
        # qwen-plus 应该在 qwen-turbo 前面（优先级更高）
        assert FALLBACK_MODEL_PREFERENCES.index("qwen-plus") < FALLBACK_MODEL_PREFERENCES.index("qwen-turbo")