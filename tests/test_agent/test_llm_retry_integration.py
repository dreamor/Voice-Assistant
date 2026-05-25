"""LLM Client 重试与模型回退集成测试

测试 call_llm_with_tools 和 call_llm_with_tools_stream 的重试循环、
指数退避、模型回退逻辑。
"""
from unittest.mock import MagicMock, patch

import litellm
import pytest

from voice_assistant.agent.llm_client import call_llm_with_tools, call_llm_with_tools_stream


def _make_model(name="primary", litellm_name="openai/primary"):
    model = MagicMock()
    model.name = name
    model.litellm_model = litellm_name
    model.base_url = "http://localhost"
    model.api_key = "test-key"
    return model


def _setup_single_model(mock_mm):
    """配置单个模型（无回退）"""
    mock_model = _make_model()
    queue = MagicMock()
    queue.models = [mock_model]
    queue.has_fallback.return_value = False
    mock_mm.get_queue.return_value = queue
    mock_mm.get_current_model.return_value = mock_model
    mock_mm.build_model_queue.return_value = None


def _setup_two_models(mock_mm):
    """配置主+备用两个模型"""
    primary = _make_model("primary", "openai/primary")
    fallback = _make_model("fallback", "openai/fallback")
    queue = MagicMock()
    queue.models = [primary, fallback]
    queue.has_fallback.side_effect = [True, False]
    mock_mm.get_queue.return_value = queue
    mock_mm.get_current_model.side_effect = [primary, fallback]
    mock_mm.build_model_queue.return_value = None


def _make_response(content="hello", finish_reason="stop", tool_calls=None):
    """创建 litellm 格式的同步响应"""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


class TestRetryExhaustedSingleModel:
    """单模型：重试耗尽后返回错误"""

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_retries_on_timeout(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        mock_completion.side_effect = litellm.Timeout(
            message="timeout", model="primary", llm_provider="openai"
        )
        _setup_single_model(mock_mm)

        result = call_llm_with_tools("hello", [])
        assert result["finish_reason"] == "error"
        assert "超时" in result["content"]
        # Should have retried max_retries (3) times
        assert mock_completion.call_count == 4  # 1 initial + 3 retries

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_retries_on_rate_limit(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        mock_completion.side_effect = litellm.RateLimitError(
            message="rate limited", model="primary", llm_provider="openai"
        )
        _setup_single_model(mock_mm)

        result = call_llm_with_tools("hello", [])
        assert result["finish_reason"] == "error"
        assert "频繁" in result["content"]

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_non_retryable_error_no_retry(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        """非可重试错误（如 CLIENT_ERROR）不重试"""
        mock_completion.side_effect = litellm.BadRequestError(
            message="bad request", model="primary", llm_provider="openai"
        )
        _setup_single_model(mock_mm)

        result = call_llm_with_tools("hello", [])
        assert result["finish_reason"] == "error"
        # Should only call once (no retries for non-retryable errors)
        assert mock_completion.call_count == 1


class TestModelFallback:
    """主模型失败后回退到备用模型"""

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_fallback_on_server_error(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        """主模型 500 错误后切换到备用模型"""
        primary = _make_model("primary", "openai/primary")
        fallback = _make_model("fallback", "openai/fallback")
        queue = MagicMock()
        queue.models = [primary, fallback]
        queue.has_fallback.side_effect = [True, False]
        mock_mm.get_queue.return_value = queue
        mock_mm.get_current_model.side_effect = [primary, primary, primary, primary, fallback]
        mock_mm.build_model_queue.return_value = None

        # Primary fails all retries, fallback succeeds
        mock_completion.side_effect = [
            litellm.APIError(message="500", model="primary", llm_provider="openai", status_code=500),
            litellm.APIError(message="500", model="primary", llm_provider="openai", status_code=500),
            litellm.APIError(message="500", model="primary", llm_provider="openai", status_code=500),
            litellm.APIError(message="500", model="primary", llm_provider="openai", status_code=500),
            _make_response("fallback response"),
        ]

        result = call_llm_with_tools("hello", [])
        assert result["finish_reason"] == "stop"
        assert result["content"] == "fallback response"

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_all_models_fail(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        """所有模型都失败时返回错误"""
        mock_completion.side_effect = litellm.APIError(
            message="500", model="primary", llm_provider="openai", status_code=500
        )
        _setup_single_model(mock_mm)

        result = call_llm_with_tools("hello", [])
        assert result["finish_reason"] == "error"
        assert "不可用" in result["content"]


class TestRetryThenSuccess:
    """重试后成功"""

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_succeeds_after_retry(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        """第一次超时，第二次成功"""
        _setup_single_model(mock_mm)
        mock_completion.side_effect = [
            litellm.Timeout(message="timeout", model="primary", llm_provider="openai"),
            _make_response("recovered!"),
        ]

        result = call_llm_with_tools("hello", [])
        assert result["finish_reason"] == "stop"
        assert result["content"] == "recovered!"
        assert mock_completion.call_count == 2

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_resets_to_primary_after_success(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        """成功后 reset_to_primary 被调用"""
        _setup_single_model(mock_mm)
        mock_completion.return_value = _make_response("ok")

        result = call_llm_with_tools("hello", [])
        assert result["finish_reason"] == "stop"
        mock_mm.reset_to_primary.assert_called_once()


class TestStreamRetry:
    """流式调用的重试逻辑"""

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_stream_retries_on_error(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        """流式请求超时后重试成功"""
        _setup_single_model(mock_mm)

        # First call: timeout; second call: success
        success_chunk = MagicMock()
        success_chunk.choices = [MagicMock()]
        success_chunk.choices[0].delta = MagicMock()
        success_chunk.choices[0].delta.content = "recovered"
        success_chunk.choices[0].delta.tool_calls = None
        success_chunk.choices[0].finish_reason = "stop"

        mock_completion.side_effect = [
            litellm.Timeout(message="timeout", model="primary", llm_provider="openai"),
            iter([success_chunk]),
        ]

        events = list(call_llm_with_tools_stream("hello", []))
        token_events = [e for e in events if e.type == "token"]
        done_events = [e for e in events if e.type == "done"]
        assert len(token_events) == 1
        assert token_events[0].content == "recovered"
        assert mock_completion.call_count == 2

    @patch("voice_assistant.agent.llm_client.time.sleep")
    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    @patch("voice_assistant.agent.llm_client.litellm.completion")
    def test_stream_all_retries_exhausted(self, mock_completion, mock_mm, mock_limiter, mock_validate, mock_sleep):
        """流式请求所有重试耗尽后返回错误"""
        mock_completion.side_effect = litellm.Timeout(
            message="timeout", model="primary", llm_provider="openai"
        )
        _setup_single_model(mock_mm)

        events = list(call_llm_with_tools_stream("hello", []))
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) == 1
        assert "超时" in error_events[0].content


class TestRateLimitInput:
    """测试速率限制"""

    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    def test_rate_limit_error_sync(self, mock_mm, mock_limiter, mock_validate):
        from voice_assistant.security.validation import RateLimitError

        mock_limiter.check.side_effect = RateLimitError("too many")
        _setup_single_model(mock_mm)

        result = call_llm_with_tools("hello", [])
        assert result["finish_reason"] == "error"
        assert "频繁" in result["content"]

    @patch("voice_assistant.agent.llm_client.validate_text_input", side_effect=lambda x: x)
    @patch("voice_assistant.agent.llm_client.llm_limiter")
    @patch("voice_assistant.agent.llm_client.model_manager")
    def test_rate_limit_error_stream(self, mock_mm, mock_limiter, mock_validate):
        from voice_assistant.security.validation import RateLimitError

        mock_limiter.check.side_effect = RateLimitError("too many")
        _setup_single_model(mock_mm)

        events = list(call_llm_with_tools_stream("hello", []))
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) == 1
        assert "频繁" in error_events[0].content
