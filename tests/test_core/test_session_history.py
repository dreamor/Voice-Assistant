"""VoiceSession 历史裁剪测试

验证 token 估算和轮次/token 双重裁剪逻辑。
"""
from voice_assistant.core.session import VoiceSession


def _make_history(n: int, content_per_msg: str = "你好世界") -> list[dict]:
    """生成 n 条交替的 user/assistant 消息。"""
    messages = []
    for i in range(n):
        messages.append({"role": "user", "content": f"{content_per_msg} {i}"})
        messages.append({"role": "assistant", "content": f"回复 {i}"})
    return messages


class TestEstimateTokens:
    def test_empty_messages(self):
        session = VoiceSession()
        assert session._estimate_tokens([]) == 0

    def test_chinese_text(self):
        session = VoiceSession()
        # 纯中文：10 个中文字符 ≈ 10/1.5 ≈ 6 tokens + 4 开销
        msgs = [{"role": "user", "content": "你好世界你好世界你好世界"}]
        tokens = session._estimate_tokens(msgs)
        assert 5 <= tokens <= 15  # 粗略范围

    def test_english_text(self):
        session = VoiceSession()
        # 纯英文：40 字符 ≈ 10 tokens + 4 开销
        msgs = [{"role": "user", "content": "Hello world, this is a test."}]
        tokens = session._estimate_tokens(msgs)
        assert 5 <= tokens <= 20

    def test_system_message_preserved(self):
        session = VoiceSession()
        msgs = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好"},
        ]
        tokens = session._estimate_tokens(msgs)
        assert tokens > 0

    def test_none_content_handled(self):
        session = VoiceSession()
        msgs = [{"role": "assistant", "content": None, "tool_calls": []}]
        tokens = session._estimate_tokens(msgs)
        # 只计入角色开销 4 tokens
        assert tokens == 4


class TestTrimHistoryByTurns:
    def test_trim_by_turn_count(self):
        session = VoiceSession()
        session._max_history_turns = 4
        session._max_context_tokens = 1_000_000  # 设高，不触发 token 裁剪

        session._history = _make_history(10)
        session._trim_history()

        assert len(session._history) <= 4

    def test_no_trim_when_under_limit(self):
        session = VoiceSession()
        session._max_history_turns = 20
        session._max_context_tokens = 1_000_000

        session._history = _make_history(5)
        session._trim_history()

        assert len(session._history) == 10  # 5 轮 = 10 条消息


class TestTrimHistoryByTokens:
    def test_trim_by_token_limit(self):
        session = VoiceSession()
        session._max_history_turns = 1000  # 设高，不触发轮次裁剪
        session._max_context_tokens = 50  # 非常低的 token 上限

        # 10 轮 = 20 条消息，每条约 10+ tokens，总计远超 50
        session._history = _make_history(10)
        session._trim_history()

        # 裁剪后 token 数应 <= 上限
        assert session._estimate_tokens(session._history) <= session._max_context_tokens

    def test_system_messages_never_removed(self):
        session = VoiceSession()
        session._max_history_turns = 1000
        session._max_context_tokens = 30  # 极低上限

        system_msg = {"role": "system", "content": "你是一个语音助手，帮助用户完成各种任务。"}
        session._history = [system_msg] + _make_history(5)
        session._trim_history()

        # 系统消息保留
        assert system_msg in session._history

    def test_trim_removes_oldest_first(self):
        session = VoiceSession()
        session._max_history_turns = 1000
        session._max_context_tokens = 80

        session._history = _make_history(10)
        original_first = session._history[0]
        session._trim_history()

        # 最旧的消息应被移除
        assert original_first not in session._history

    def test_no_trim_when_tokens_under_limit(self):
        session = VoiceSession()
        session._max_history_turns = 1000
        session._max_context_tokens = 1_000_000

        session._history = _make_history(3)
        session._trim_history()

        # 不触发 token 裁剪，消息数量不变
        assert len(session._history) == 6


class TestSetHistory:
    def test_set_history_trims(self):
        session = VoiceSession()
        session._max_history_turns = 4
        session._max_context_tokens = 1_000_000

        session.set_history(_make_history(20))
        assert len(session._history) <= 4

    def test_get_history_returns_copy(self):
        session = VoiceSession()
        session._history = [{"role": "user", "content": "hi"}]

        h = session.get_history()
        h.append({"role": "assistant", "content": "hey"})

        assert len(session._history) == 1  # 原始不受影响
