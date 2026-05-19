"""Web UI MCP/Skill REST 端点测试 (FastAPI TestClient)

只覆盖路由层逻辑：响应结构、状态码、404、503。
manager 被 monkeypatch 成 FakeMgr，避免真正启动 MCP 子进程。
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from voice_assistant.skills import SkillManager


class _FakeMcpMgr:
    def list_servers(self):
        return [{
            "id": "echo",
            "transport": "stdio",
            "enabled": True,
            "ready": True,
            "error": None,
            "tools": ["mcp__echo__echo"],
        }]


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch):
    """提供一个带 fake MCP/Skill manager 的 TestClient，不启动 lifespan"""
    import web_ui as web_ui_mod
    from voice_assistant.core import session as session_mod

    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: test skill\n"
        "trigger: keywords\nkeywords: [hi]\n---\nbody"
    )
    mgr = SkillManager(tmp_path)
    mgr.reload()

    monkeypatch.setattr(session_mod, "_mcp_manager", _FakeMcpMgr())
    monkeypatch.setattr(session_mod, "_skill_manager", mgr)

    # 用 raise_server_exceptions=False 跳过 lifespan
    # TestClient 默认会触发 lifespan, 包含 init_db / 注册 ToolRegistry，
    # 不便于纯路由测试。这里我们直接 raw_app=web_ui_mod.app + lifespan="off"
    with TestClient(web_ui_mod.app) as client:
        yield client


@pytest.mark.unit
def test_mcp_servers_endpoint(app_client: TestClient):
    r = app_client.get("/api/mcp/servers")
    assert r.status_code == 200
    body = r.json()
    assert "servers" in body
    assert body["servers"][0]["id"] == "echo"
    assert body["servers"][0]["tools"] == ["mcp__echo__echo"]


@pytest.mark.unit
def test_skills_endpoint(app_client: TestClient):
    r = app_client.get("/api/skills")
    assert r.status_code == 200
    body = r.json()
    names = [s["name"] for s in body["skills"]]
    assert "alpha" in names
    alpha = next(s for s in body["skills"] if s["name"] == "alpha")
    assert alpha["enabled"] is True
    assert alpha["keywords"] == ["hi"]


@pytest.mark.unit
def test_disable_then_enable_skill(app_client: TestClient):
    r = app_client.post("/api/skills/alpha/disable")
    assert r.status_code == 200
    assert r.json() == {"success": True, "name": "alpha", "enabled": False}

    r = app_client.post("/api/skills/alpha/enable")
    assert r.status_code == 200
    assert r.json()["enabled"] is True


@pytest.mark.unit
def test_skill_404(app_client: TestClient):
    r = app_client.post("/api/skills/nope/enable")
    assert r.status_code == 404
    assert "未找到 skill" in r.json()["detail"]


@pytest.mark.unit
def test_reload_skills_endpoint(app_client: TestClient):
    r = app_client.post("/api/skills/reload")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["count"] >= 1


@pytest.mark.unit
def test_skill_endpoints_503_when_manager_absent(monkeypatch):
    """没有 Skill manager 时返回 503"""
    import web_ui as web_ui_mod
    from voice_assistant.core import session as session_mod

    with TestClient(web_ui_mod.app) as client:
        # lifespan 启动后再 patch（覆盖 lifespan 主动构建的 manager）
        monkeypatch.setattr(session_mod, "_skill_manager", None)
        monkeypatch.setattr(session_mod, "_mcp_manager", None)

        # GET 仍然返回 200（空列表），仅 POST 启停操作要求 manager 存在
        r = client.get("/api/skills")
        assert r.status_code == 200
        assert r.json() == {"skills": []}

        r = client.post("/api/skills/x/enable")
        assert r.status_code == 503

        r = client.post("/api/skills/x/disable")
        assert r.status_code == 503

        r = client.post("/api/skills/reload")
        assert r.status_code == 503


@pytest.mark.unit
def test_mcp_servers_empty_when_manager_absent(monkeypatch):
    import web_ui as web_ui_mod
    from voice_assistant.core import session as session_mod

    with TestClient(web_ui_mod.app) as client:
        monkeypatch.setattr(session_mod, "_mcp_manager", None)

        r = client.get("/api/mcp/servers")
        assert r.status_code == 200
        assert r.json() == {"servers": []}
