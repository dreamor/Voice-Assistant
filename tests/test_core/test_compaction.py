"""上下文压缩测试"""
from unittest.mock import patch

from voice_assistant.core.compaction import (
    compact,
    estimate_tokens,
    should_compact,
)


class TestEstimateTokens:
    def test_empty_messages(self):
        assert estimate_tokens([]) == 0

    def test_english_text(self):
        messages = [{"role": "user", "content": "Hello world"}]
        tokens = estimate_tokens(messages)
        assert tokens > 0

    def test_chinese_text(self):
        messages = [{"role": "user", "content": "你好世界"}]
        tokens = estimate_tokens(messages)
        assert tokens > 0

    def test_none_content(self):
        messages = [{"role": "assistant", "content": None}]
        tokens = estimate_tokens(messages)
        assert tokens > 0

    def test_system_message(self):
        messages = [{"role": "system", "content": "You are helpful"}]
        tokens = estimate_tokens(messages)
        assert tokens > 0


class TestShouldCompact:
    def test_no_compact_needed(self):
        messages = [{"role": "user", "content": "hi"}]
        assert should_compact(messages, max_context_tokens=6000) is False

    def test_compact_needed(self):
        # 大量消息超过阈值
        messages = [{"role": "user", "content": "这是一段很长的对话内容" * 100}] * 50
        assert should_compact(messages, max_context_tokens=1000) is True


class TestCompact:
    def test_no_compaction_needed(self):
        messages = [{"role": "user", "content": "hi"}]
        result = compact(messages, max_context_tokens=6000)
        assert result.messages_removed == 0
        assert result.messages_kept == 1

    @patch("voice_assistant.core.compaction._call_llm_for_summary")
    def test_compaction_removes_old_messages(self, mock_llm):
        mock_llm.return_value = "用户讨论了天气和旅行计划"

        # 创建足够多的消息使其超过 token 限制
        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": f"这是第{i}条消息，内容比较长" * 10})
            messages.append({"role": "assistant", "content": f"回复第{i}条" * 10})

        result = compact(messages, max_context_tokens=2000, keep_recent_tokens=500)
        assert result.messages_removed > 0
        assert result.summary == "用户讨论了天气和旅行计划"

    @patch("voice_assistant.core.compaction._call_llm_for_summary")
    def test_compaction_fallback_on_llm_failure(self, mock_llm):
        mock_llm.return_value = ""

        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": f"消息{i}" * 50})

        result = compact(messages, max_context_tokens=2000, keep_recent_tokens=500)
        assert result.messages_removed > 0
        assert "摘要生成失败" in result.summary

    def test_compaction_preserves_recent_messages(self):
        """确保最近的消息不被压缩"""
        messages = [
            {"role": "user", "content": "很早的消息" * 50},
            {"role": "assistant", "content": "早期回复" * 50},
            {"role": "user", "content": "最近的问题"},
            {"role": "assistant", "content": "最近的回答"},
        ]

        with patch("voice_assistant.core.compaction._call_llm_for_summary") as mock_llm:
            mock_llm.return_value = "早期对话摘要"
            result = compact(messages, max_context_tokens=500, keep_recent_tokens=200)

        # 最近的消息应该保留
        assert result.messages_kept > 0
