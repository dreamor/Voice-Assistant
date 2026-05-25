"""MCP config 加载 + bridge 字符串化单测"""
from pathlib import Path

import pytest

from voice_assistant.tools.mcp.bridge import _stringify_mcp_result
from voice_assistant.tools.mcp.config import _resolve_secrets, load_servers


@pytest.mark.unit
def test_resolve_secrets_simple():
    secrets = {"mcp": {"github": {"token": "ghp_xxx"}}}
    assert _resolve_secrets("${secrets.mcp.github.token}", secrets) == "ghp_xxx"


@pytest.mark.unit
def test_resolve_secrets_missing_keeps_placeholder():
    out = _resolve_secrets("${secrets.missing.key}", {})
    assert out == "${secrets.missing.key}"


@pytest.mark.unit
def test_resolve_secrets_non_string_passthrough():
    # 非字符串值应原样返回
    assert _resolve_secrets(42, {}) == 42  # type: ignore[arg-type]


@pytest.mark.unit
def test_load_servers_from_yaml(tmp_path: Path):
    servers_yaml = tmp_path / "mcp.yaml"
    servers_yaml.write_text(
        """
servers:
  - id: echo
    transport: stdio
    command: ["python3", "-m", "echo"]
    security_default: read_only
  - {}  # 缺 id，应被跳过
"""
    )
    servers = load_servers(servers_yaml)
    assert len(servers) == 1
    assert servers[0].id == "echo"
    assert servers[0].transport == "stdio"
    assert servers[0].command == ["python3", "-m", "echo"]
    assert servers[0].security_default == "read_only"


@pytest.mark.unit
def test_load_servers_substitutes_secrets(tmp_path: Path):
    secrets_yaml = tmp_path / "secrets.yaml"
    secrets_yaml.write_text("mcp:\n  github:\n    token: ghp_test\n")

    servers_yaml = tmp_path / "mcp.yaml"
    servers_yaml.write_text(
        """
servers:
  - id: github
    transport: stdio
    command: ["npx", "-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: ${secrets.mcp.github.token}
"""
    )
    servers = load_servers(servers_yaml, secrets_path=secrets_yaml)
    assert servers[0].env["GITHUB_TOKEN"] == "ghp_test"


@pytest.mark.unit
def test_load_servers_missing_file(tmp_path: Path):
    assert load_servers(tmp_path / "nope.yaml") == []


@pytest.mark.unit
def test_load_servers_sse_and_http(tmp_path: Path):
    """SSE + HTTP transport 解析"""
    servers_yaml = tmp_path / "mcp.yaml"
    servers_yaml.write_text(
        """
servers:
  - id: sse_demo
    transport: sse
    url: https://example.com/sse
    headers:
      Authorization: Bearer token123
  - id: http_demo
    transport: http
    url: https://example.com/mcp
    enabled: false
    security_default: dangerous
"""
    )
    servers = load_servers(servers_yaml)
    assert {s.id for s in servers} == {"sse_demo", "http_demo"}
    sse = next(s for s in servers if s.id == "sse_demo")
    http = next(s for s in servers if s.id == "http_demo")
    assert sse.transport == "sse"
    assert sse.url == "https://example.com/sse"
    assert sse.headers == {"Authorization": "Bearer token123"}
    assert http.transport == "http"
    assert http.enabled is False
    assert http.security_default == "dangerous"


@pytest.mark.unit
def test_meta_tool_lists_servers_when_no_manager(monkeypatch):
    """list_mcp_servers 在无 manager 时给出友好提示"""
    from voice_assistant.core.lifecycle import get_lifecycle
    from voice_assistant.tools.mcp import get_mcp_meta_tools

    lc = get_lifecycle()
    monkeypatch.setattr(lc, "_mcp_manager", None)
    tools = get_mcp_meta_tools()
    tool = next(t for t in tools if t.name == "list_mcp_servers")
    assert "MCP 未启用" in tool.handler()


class _FakeContent:
    def __init__(self, text: str):
        self.text = text


class _FakeResult:
    def __init__(self, items, is_error=False):
        self.content = items
        self.isError = is_error


@pytest.mark.unit
def test_stringify_mcp_result_joins_text_parts():
    result = _FakeResult([_FakeContent("hello"), _FakeContent("world")])
    assert _stringify_mcp_result(result) == "hello\nworld"


@pytest.mark.unit
def test_stringify_mcp_result_marks_error():
    result = _FakeResult([_FakeContent("oops")], is_error=True)
    assert _stringify_mcp_result(result) == "[MCP error] oops"


@pytest.mark.unit
def test_stringify_mcp_result_none():
    assert _stringify_mcp_result(None) == ""


# ----- bridge.make_tool_definition handler 行为 -----

@pytest.mark.unit
def test_make_tool_definition_handler_success():
    """handler 阻塞调度异步 call_tool，返回 stringify 结果"""
    import asyncio
    import threading

    from voice_assistant.tools.mcp.bridge import make_tool_definition

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        async def fake_call_tool(name, args):
            return _FakeResult([_FakeContent(f"called:{name}:{args.get('x')}")])

        td = make_tool_definition(
            server_id="srv",
            mcp_tool_name="op",
            description="desc",
            input_schema={"type": "object"},
            call_tool=fake_call_tool,
            loop=loop,
            security_default="read_only",
        )
        assert td.name == "mcp__srv__op"

        from voice_assistant.security.safe_guard import SecurityLevel
        assert td.security_level == SecurityLevel.READ_ONLY

        result = td.handler(x="hi")
        assert result == "called:op:hi"
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


@pytest.mark.unit
def test_make_tool_definition_handler_propagates_async_exception():
    import asyncio
    import threading

    from voice_assistant.tools.mcp.bridge import make_tool_definition

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        async def boom(_name, _args):
            raise RuntimeError("inner failure")

        td = make_tool_definition(
            server_id="srv",
            mcp_tool_name="boom",
            description="",
            input_schema={"type": "object", "properties": {}},
            call_tool=boom,
            loop=loop,
        )
        result = td.handler()
        assert "调用失败" in result
        assert "inner failure" in result
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


@pytest.mark.unit
def test_make_tool_definition_default_security_level_write():
    import asyncio

    from voice_assistant.security.safe_guard import SecurityLevel
    from voice_assistant.tools.mcp.bridge import make_tool_definition

    loop = asyncio.new_event_loop()
    try:
        td = make_tool_definition(
            server_id="srv",
            mcp_tool_name="op",
            description="",
            input_schema={},
            call_tool=lambda *a: None,
            loop=loop,
            security_default="invalid_level_falls_back",
        )
        # 非法 level 回落到 WRITE
        assert td.security_level == SecurityLevel.WRITE
    finally:
        loop.close()


@pytest.mark.unit
def test_stringify_mcp_result_string_fallback():
    """没有 content 属性时返回 str(result)"""
    assert _stringify_mcp_result("plain string") == "plain string"


@pytest.mark.unit
def test_stringify_mcp_result_mixed_content():
    """content list 混合文本和未识别项"""
    class _ImageContent:
        type = "image"

        def __str__(self):
            return "<image>"

    result = _FakeResult([_FakeContent("text-a"), _ImageContent()])
    out = _stringify_mcp_result(result)
    assert "text-a" in out
    assert "<image>" in out
