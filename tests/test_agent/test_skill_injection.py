"""测试 llm_client._build_messages 接收 extra_system"""
import pytest

from voice_assistant.agent.llm_client import AGENT_SYSTEM_PROMPT, _build_messages


@pytest.mark.unit
def test_build_messages_default_system_prompt():
    msgs = _build_messages("hello")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == AGENT_SYSTEM_PROMPT
    assert msgs[-1] == {"role": "user", "content": "hello"}


@pytest.mark.unit
def test_build_messages_appends_extra_system():
    msgs = _build_messages("hello", extra_system="## Skill body\nuse echo")
    assert msgs[0]["role"] == "system"
    content = msgs[0]["content"]
    assert AGENT_SYSTEM_PROMPT in content
    assert content.endswith("## Skill body\nuse echo")


@pytest.mark.unit
def test_build_messages_empty_extra_system_keeps_prompt_unchanged():
    msgs = _build_messages("hi", extra_system="")
    assert msgs[0]["content"] == AGENT_SYSTEM_PROMPT


@pytest.mark.unit
def test_build_messages_with_history():
    history = [
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "ack"},
    ]
    msgs = _build_messages("now", conversation_history=history, extra_system="X")
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"] == "now"
    assert msgs[0]["content"].endswith("X")
