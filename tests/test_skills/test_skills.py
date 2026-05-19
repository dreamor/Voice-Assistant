"""Skill 加载、selector、deps、manager 单测"""
from pathlib import Path

import pytest

from voice_assistant.skills.deps import _python_package_available, check_skill
from voice_assistant.skills.loader import parse_skill_md, scan_skills
from voice_assistant.skills.manager import SkillManager
from voice_assistant.skills.models import Skill, SkillDependencies
from voice_assistant.skills.selector import (
    build_system_prompt_addendum,
    select_for_message,
)

# ----- loader -----

@pytest.mark.unit
def test_parse_skill_md_minimal(tmp_path: Path):
    text = (
        "---\nname: hello\ndescription: hi\n---\n\n"
        "## body\n\nmarkdown content"
    )
    s = parse_skill_md(text, tmp_path / "SKILL.md")
    assert s is not None
    assert s.name == "hello"
    assert s.trigger == "manual"
    assert s.keywords == ()
    assert "markdown content" in s.body


@pytest.mark.unit
def test_parse_skill_md_full(tmp_path: Path):
    text = (
        "---\n"
        "name: github-triage\n"
        "description: triage\n"
        "trigger: keywords\n"
        "keywords: [issue, triage]\n"
        "required_mcp_servers: [github]\n"
        "required_python: [requests>=2.31]\n"
        "required_env: [GITHUB_TOKEN]\n"
        "---\n\n"
        "body"
    )
    s = parse_skill_md(text, tmp_path / "SKILL.md")
    assert s is not None
    assert s.trigger == "keywords"
    assert s.keywords == ("issue", "triage")
    assert s.deps.mcp_servers == ("github",)
    assert s.deps.python == ("requests>=2.31",)
    assert s.deps.env == ("GITHUB_TOKEN",)


@pytest.mark.unit
def test_parse_skill_md_missing_frontmatter(tmp_path: Path):
    assert parse_skill_md("no frontmatter here", tmp_path / "SKILL.md") is None


@pytest.mark.unit
def test_parse_skill_md_invalid_trigger_falls_back(tmp_path: Path):
    text = "---\nname: x\ntrigger: nonsense\n---\n\nbody"
    s = parse_skill_md(text, tmp_path / "SKILL.md")
    assert s is not None
    assert s.trigger == "manual"


@pytest.mark.unit
def test_scan_skills_recursive(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "SKILL.md").write_text(
        "---\nname: a\n---\n\nbody-a"
    )
    (tmp_path / "b" / "c").mkdir(parents=True)
    (tmp_path / "b" / "c" / "SKILL.md").write_text(
        "---\nname: b\n---\n\nbody-b"
    )
    skills = scan_skills(tmp_path)
    assert {s.name for s in skills} == {"a", "b"}


@pytest.mark.unit
def test_scan_skills_missing_root(tmp_path: Path):
    assert scan_skills(tmp_path / "nope") == []


# ----- selector -----

def _mk_skill(
    name: str, trigger: str = "keywords", keywords: tuple = (), enabled: bool = True
) -> Skill:
    return Skill(
        name=name, description=name, trigger=trigger,  # type: ignore[arg-type]
        keywords=keywords, body=f"body of {name}",
        path=Path(f"/{name}"), enabled=enabled,
    )


@pytest.mark.unit
def test_select_for_message_matches_keyword():
    skills = [
        _mk_skill("a", keywords=("hello",)),
        _mk_skill("b", keywords=("world",)),
    ]
    out = select_for_message(skills, "say HELLO friend")
    assert [s.name for s in out] == ["a"]


@pytest.mark.unit
def test_select_for_message_skips_disabled():
    skills = [_mk_skill("a", keywords=("hello",), enabled=False)]
    assert select_for_message(skills, "hello") == []


@pytest.mark.unit
def test_select_for_message_ignores_always_and_manual():
    skills = [
        _mk_skill("always", trigger="always"),
        _mk_skill("manual", trigger="manual"),
        _mk_skill("kw", trigger="keywords", keywords=("hello",)),
    ]
    out = select_for_message(skills, "hello there")
    assert [s.name for s in out] == ["kw"]


@pytest.mark.unit
def test_build_system_prompt_addendum_separates_always_and_other():
    skills = [
        _mk_skill("always_one", trigger="always"),
        _mk_skill("kw_one", trigger="keywords", keywords=("foo",)),
    ]
    out = build_system_prompt_addendum(skills)
    assert "## 始终启用的 Skill" in out
    assert "body of always_one" in out
    assert "## 可用 Skill" in out
    assert "kw_one" in out


# ----- deps -----

@pytest.mark.unit
def test_python_package_available_handles_version_spec():
    # pytest 本身一定存在
    assert _python_package_available("pytest>=1.0")
    assert not _python_package_available("non_existent_module_xyz_99")


@pytest.mark.unit
def test_check_skill_returns_missing():
    skill = Skill(
        name="s", description="d", trigger="manual", keywords=(),
        body="", path=Path("/s"),
        deps=SkillDependencies(
            mcp_servers=("missing_mcp",),
            python=("non_existent_module_xyz_99",),
            env=("UNSET_VAR_FOR_TEST_XYZ",),
        ),
    )
    check = check_skill(skill, available_mcp_servers=[])
    assert not check.ok
    assert "missing_mcp" in check.missing_mcp_servers
    assert "non_existent_module_xyz_99" in check.missing_python
    assert "UNSET_VAR_FOR_TEST_XYZ" in check.missing_env


@pytest.mark.unit
def test_check_skill_ok_when_all_satisfied():
    skill = Skill(
        name="s", description="d", trigger="manual", keywords=(),
        body="", path=Path("/s"),
        deps=SkillDependencies(
            mcp_servers=("present",), python=("pytest",), env=("PATH",),
        ),
    )
    check = check_skill(skill, available_mcp_servers=["present"])
    assert check.ok


# ----- manager -----

@pytest.mark.unit
def test_manager_set_enabled(tmp_path: Path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "SKILL.md").write_text(
        "---\nname: x\n---\n\nbody"
    )
    mgr = SkillManager(tmp_path)
    mgr.reload()
    assert mgr.get("x").enabled is True
    assert mgr.set_enabled("x", False) is True
    assert mgr.get("x").enabled is False
    assert mgr.set_enabled("nope", False) is False


# ----- addendum for message -----

@pytest.mark.unit
def test_build_addendum_for_message_combines_always_and_hit(tmp_path: Path):
    from voice_assistant.skills.selector import build_addendum_for_message

    always = _mk_skill("always_one", trigger="always")
    hit = _mk_skill("kw_one", trigger="keywords", keywords=("foo",))
    miss = _mk_skill("kw_two", trigger="keywords", keywords=("bar",))
    out = build_addendum_for_message([always, hit, miss], "this contains foo")
    assert "always_one" in out
    assert "body of always_one" in out
    assert "kw_one" in out
    assert "body of kw_one" in out
    assert "kw_two" not in out


@pytest.mark.unit
def test_build_addendum_for_message_empty_when_no_skill():
    from voice_assistant.skills.selector import build_addendum_for_message

    assert build_addendum_for_message([], "anything") == ""


@pytest.mark.unit
def test_manager_build_addendum_for_message(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "SKILL.md").write_text(
        "---\nname: echo\ntrigger: keywords\nkeywords: [echo]\n---\n\nuse echo tool"
    )
    mgr = SkillManager(tmp_path)
    mgr.reload()
    out = mgr.build_addendum_for_message("please echo something")
    assert "use echo tool" in out
    assert mgr.build_addendum_for_message("no match here") == ""
