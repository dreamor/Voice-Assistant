"""MCP meta tools (list_mcp_servers) 输出格式测试"""
import pytest

from voice_assistant.tools.mcp.meta_tools import get_mcp_meta_tools


def _tool():
    return next(t for t in get_mcp_meta_tools() if t.name == "list_mcp_servers")


class _FakeMgr:
    def __init__(self, servers):
        self._servers = servers

    def list_servers(self):
        return self._servers


@pytest.mark.unit
def test_list_mcp_servers_no_manager(monkeypatch):
    from voice_assistant.core.lifecycle import get_lifecycle
    lc = get_lifecycle()
    monkeypatch.setattr(lc, "_mcp_manager", None)

    out = _tool().handler()
    assert "未启用" in out or "没有配置" in out


@pytest.mark.unit
def test_list_mcp_servers_empty(monkeypatch):
    from voice_assistant.core.lifecycle import get_lifecycle
    lc = get_lifecycle()
    monkeypatch.setattr(lc, "_mcp_manager", _FakeMgr([]))

    out = _tool().handler()
    assert "暂无" in out


@pytest.mark.unit
def test_list_mcp_servers_renders_ok_and_fail(monkeypatch):
    from voice_assistant.core.lifecycle import get_lifecycle
    lc = get_lifecycle()
    monkeypatch.setattr(lc, "_mcp_manager", _FakeMgr([
        {
            "id": "good",
            "transport": "stdio",
            "enabled": True,
            "ready": True,
            "error": None,
            "tools": ["mcp__good__op"],
        },
        {
            "id": "bad",
            "transport": "sse",
            "enabled": True,
            "ready": False,
            "error": "connection refused",
            "tools": [],
        },
    ]))

    out = _tool().handler()
    assert "good" in out
    assert "bad" in out
    assert "connection refused" in out
