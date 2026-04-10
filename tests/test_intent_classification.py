"""Tests for intent classification (keyword + LLM-based)."""
import json
from unittest.mock import MagicMock, patch

from voice_assistant.model.intent import IntentType
from voice_assistant.services.router import (
    _keyword_classify_intent,
    llm_classify_intent,
    simple_classify_intent,
)


class TestKeywordClassify:
    """Test keyword-based intent classification (fallback logic)."""

    def test_computer_control_keywords(self):
        """Computer control keywords trigger computer_control intent."""
        for phrase in [
            "打开计算器",
            "关闭这个程序",
            "截屏",
            "新建文件夹",
            "运行Python脚本",
            "复制文件",
            "删除这个文件",
            "帮我操作一下电脑",
        ]:
            intent = _keyword_classify_intent(phrase)
            assert intent.intent_type == IntentType.COMPUTER_CONTROL, (
                f"'{phrase}' should be COMPUTER_CONTROL"
            )
            assert intent.confidence == 0.7

    def test_ordinary_chat(self):
        """Phrases without action keywords or question marks trigger ordinary_chat."""
        for phrase in [
            "你好",
            "今天天气怎么样",
            "北京现在天气晴朗",
            "给我讲个笑话",
            "你是谁",
        ]:
            intent = _keyword_classify_intent(phrase)
            assert intent.intent_type == IntentType.ORDINARY_CHAT, (
                f"'{phrase}' should be ORDINARY_CHAT"
            )
            assert intent.confidence == 0.5

    def test_query_answer_with_chinese_question_mark(self):
        """Phrases with Chinese question mark trigger query_answer."""
        for phrase in [
            "今天天气怎么样？",
            "北京的气温是多少？",
            "你知道现在几点了吗？",
        ]:
            intent = _keyword_classify_intent(phrase)
            assert intent.intent_type == IntentType.QUERY_ANSWER
            assert intent.confidence == 0.6

    def test_query_answer_with_english_question_mark(self):
        """Phrases with English question mark trigger query_answer."""
        intent = _keyword_classify_intent("What time is it?")
        assert intent.intent_type == IntentType.QUERY_ANSWER


class TestLLMClassify:
    """Test LLM-based intent classification."""

    def test_llm_classify_computer_control(self):
        """LLM returns computer_control intent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "intent_type": "computer_control",
                "confidence": 0.95,
            })}}]
        }

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.return_value = mock_response
            intent = llm_classify_intent("帮我打开计算器")

        assert intent is not None
        assert intent.intent_type == IntentType.COMPUTER_CONTROL
        assert intent.confidence == 0.95

    def test_llm_classify_query_answer(self):
        """LLM returns query_answer intent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "intent_type": "query_answer",
                "confidence": 0.88,
            })}}]
        }

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.return_value = mock_response
            intent = llm_classify_intent("北京今天天气如何？")

        assert intent is not None
        assert intent.intent_type == IntentType.QUERY_ANSWER
        assert intent.confidence == 0.88

    def test_llm_classify_ordinary_chat(self):
        """LLM returns ordinary_chat intent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "intent_type": "ordinary_chat",
                "confidence": 0.92,
            })}}]
        }

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.return_value = mock_response
            intent = llm_classify_intent("你好呀")

        assert intent is not None
        assert intent.intent_type == IntentType.ORDINARY_CHAT
        assert intent.confidence == 0.92

    def test_llm_classify_http_error_returns_none(self):
        """LLM returns None on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.return_value = mock_response
            intent = llm_classify_intent("测试")

        assert intent is None

    def test_llm_classify_timeout_returns_none(self):
        """LLM returns None on timeout."""
        import requests as real_requests

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.side_effect = real_requests.Timeout("Request timed out")
            intent = llm_classify_intent("测试")

        assert intent is None

    def test_llm_classify_json_parse_error_returns_none(self):
        """LLM returns None on invalid JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not valid json"}}]
        }

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.return_value = mock_response
            intent = llm_classify_intent("测试")

        assert intent is None

    def test_llm_classify_unknown_intent_type_returns_none(self):
        """LLM returns None when intent_type is unrecognized."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "intent_type": "unknown_type",
                "confidence": 0.5,
            })}}]
        }

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.return_value = mock_response
            intent = llm_classify_intent("测试")

        assert intent is None


class TestSimpleClassifyIntent:
    """Test simple_classify_intent with LLM + fallback behavior."""

    def test_uses_llm_result_when_available(self):
        """When LLM returns valid result, it is used."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "intent_type": "query_answer",
                "confidence": 0.85,
            })}}]
        }

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.return_value = mock_response
            intent = simple_classify_intent("北京天气怎么样？")

        assert intent.intent_type == IntentType.QUERY_ANSWER
        assert intent.confidence == 0.85

    def test_fallback_to_keyword_when_llm_fails(self):
        """When LLM fails, fallback to keyword matching."""
        import requests as real_requests

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.side_effect = real_requests.ConnectionError("Network error")
            intent = simple_classify_intent("打开计算器")

        # Should fallback to keyword matching
        assert intent.intent_type == IntentType.COMPUTER_CONTROL
        assert intent.confidence == 0.7

    def test_fallback_to_keyword_when_confidence_too_low(self):
        """When LLM confidence is below 0.3, fallback to keyword matching."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "intent_type": "ordinary_chat",
                "confidence": 0.1,  # Below 0.3 threshold
            })}}]
        }

        with patch("voice_assistant.services.router.requests.post") as mock_post:
            mock_post.return_value = mock_response
            # "打开计算器" contains computer keyword, so fallback should return computer_control
            intent = simple_classify_intent("打开计算器")

        # LLM result has confidence < 0.3, so fallback to keyword
        assert intent.intent_type == IntentType.COMPUTER_CONTROL
        assert intent.confidence == 0.7
