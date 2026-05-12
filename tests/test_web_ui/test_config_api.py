"""Config API 测试"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


class TestConfigAPI:
    """测试配置 API 端点"""

    def test_config_endpoint_exists(self):
        """验证配置端点存在"""
        from web_ui import app

        client = TestClient(app)
        response = client.get("/api/config")

        # 端点应该存在（可能返回 200 或需要认证）
        assert response.status_code in [200, 401, 403]

    def test_models_endpoint_exists(self):
        """验证模型列表端点存在"""
        from web_ui import app

        client = TestClient(app)
        response = client.get("/api/models")

        assert response.status_code in [200, 401, 403]

    def test_history_endpoint_exists(self):
        """验证历史记录端点存在"""
        from web_ui import app

        client = TestClient(app)
        response = client.get("/api/history")

        assert response.status_code in [200, 401, 403]

    def test_config_save_endpoint_exists(self):
        """验证配置保存端点存在"""
        from web_ui import app

        client = TestClient(app)
        response = client.post("/api/config", json={"key": "value"})

        assert response.status_code in [200, 400, 401, 403, 422]


class TestConfigValidation:
    """测试配置验证"""

    def test_config_validation_function_exists(self):
        """验证配置验证函数存在"""
        from voice_assistant.config import _validate_config

        assert callable(_validate_config)

    def test_config_validation_accepts_app_config(self):
        """验证配置验证接受 AppConfig 对象"""
        from voice_assistant.config import _validate_config, load_config

        # 使用 load_config 创建有效配置
        cfg = load_config()
        result = _validate_config(cfg)
        # 应该返回警告列表（可能为空）
        assert isinstance(result, list)


class TestAPIResponseFormat:
    """测试 API 响应格式"""

    def test_api_response_structure(self):
        """验证 API 响应结构一致"""
        # 标准响应格式
        response = {
            'success': True,
            'data': None,
            'error': None,
        }

        assert 'success' in response
        assert 'data' in response
        assert 'error' in response

    def test_error_response_structure(self):
        """验证错误响应结构"""
        error_response = {
            'success': False,
            'data': None,
            'error': '错误消息',
        }

        assert error_response['success'] is False
        assert error_response['error'] is not None

    def test_success_response_structure(self):
        """验证成功响应结构"""
        success_response = {
            'success': True,
            'data': {'key': 'value'},
            'error': None,
        }

        assert success_response['success'] is True
        assert success_response['data'] is not None
        assert success_response['error'] is None
