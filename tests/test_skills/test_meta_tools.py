"""Skill meta tools (list/check_deps/enable/disable) 行为测试"""
import pytest

from voice_assistant.skills import SkillManager
from voice_assistant.skills.meta_tools import get_skill_meta_tools


@pytest.fixture
def loaded_manager(tmp_path, monkeypatch) -> SkillManager:
    """注入一个真实 SkillManager 到 session 模块，模拟启动后状态"""
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "SKILL.md").write_text(
        "---\nname: alpha\ntrigger: keywords\nkeywords: [a]\n"
        "description: skill alpha\nrequired_python: [pytest]\n---\nbody-alpha"
    )
    (tmp_path / "beta").mkdir()
    (tmp_path / "beta" / "SKILL.md").write_text(
        "---\nname: beta\ndescription: skill beta\n"
        "required_python: [non_existent_pkg_xyz]\n---\nbody-beta"
    )
    mgr = SkillManager(tmp_path)
    mgr.reload()

    from voice_assistant.core import session as session_mod
    monkeypatch.setattr(session_mod, "_skill_manager", mgr)
    monkeypatch.setattr(session_mod, "_mcp_manager", None)
    return mgr


def _by_name(name: str):
    for tool in get_skill_meta_tools():
        if tool.name == name:
            return tool
    raise AssertionError(f"tool {name} 不存在")


@pytest.mark.unit
def test_list_skills_no_manager(monkeypatch):
    from voice_assistant.core import session as session_mod

    monkeypatch.setattr(session_mod, "_skill_manager", None)
    out = _by_name("list_skills").handler()
    assert "未启用" in out


@pytest.mark.unit
def test_list_skills_renders_table(loaded_manager: SkillManager):
    out = _by_name("list_skills").handler()
    assert "alpha" in out
    assert "beta" in out
    assert "[keywords]" in out
    assert "[manual]" in out


@pytest.mark.unit
def test_list_skills_marks_disabled(loaded_manager: SkillManager):
    loaded_manager.set_enabled("alpha", False)
    out = _by_name("list_skills").handler()
    # ✓ for beta enabled, ✗ for alpha disabled
    assert "✗ alpha" in out
    assert "✓ beta" in out


@pytest.mark.unit
def test_check_skill_deps_unknown_skill(loaded_manager: SkillManager):
    out = _by_name("check_skill_deps").handler(name="nope")
    assert "未找到 skill" in out


@pytest.mark.unit
def test_check_skill_deps_missing_python(loaded_manager: SkillManager):
    out = _by_name("check_skill_deps").handler(name="beta")
    assert "non_existent_pkg_xyz" in out
    assert "pip install" in out


@pytest.mark.unit
def test_check_skill_deps_satisfied(loaded_manager: SkillManager):
    # alpha only depends on pytest, which is installed in dev env
    out = _by_name("check_skill_deps").handler(name="alpha")
    assert "依赖完整" in out


@pytest.mark.unit
def test_enable_disable_skill(loaded_manager: SkillManager):
    loaded_manager.set_enabled("alpha", False)
    assert "已启用" in _by_name("enable_skill").handler(name="alpha")
    assert loaded_manager.get("alpha").enabled is True

    assert "已禁用" in _by_name("disable_skill").handler(name="alpha")
    assert loaded_manager.get("alpha").enabled is False


@pytest.mark.unit
def test_enable_unknown_returns_friendly_msg(loaded_manager: SkillManager):
    assert "未找到 skill" in _by_name("enable_skill").handler(name="nope")


@pytest.mark.unit
def test_meta_tools_have_correct_security_levels():
    from voice_assistant.security.safe_guard import SecurityLevel

    levels = {t.name: t.security_level for t in get_skill_meta_tools()}
    assert levels["list_skills"] == SecurityLevel.READ_ONLY
    assert levels["check_skill_deps"] == SecurityLevel.READ_ONLY
    assert levels["enable_skill"] == SecurityLevel.WRITE
    assert levels["disable_skill"] == SecurityLevel.WRITE


@pytest.mark.unit
def test_check_deps_when_no_manager(monkeypatch):
    from voice_assistant.core import session as session_mod

    monkeypatch.setattr(session_mod, "_skill_manager", None)
    out = _by_name("check_skill_deps").handler(name="anything")
    assert "未启用" in out
