"""SKILL.md 加载器

解析 YAML frontmatter (--- ... ---) + 之后的 Markdown body。
扫描 skills/**/SKILL.md 并构造 Skill 对象。
"""
import logging
import re
from pathlib import Path

import yaml

from voice_assistant.skills.models import Skill, SkillDependencies, Trigger

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL
)


def parse_skill_md(text: str, path: Path) -> Skill | None:
    """解析 SKILL.md。返回 None 表示解析失败（已记录日志）。"""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        logger.warning(f"[Skill] 缺少 frontmatter: {path}")
        return None

    raw_meta, body = match.group(1), match.group(2).strip()
    try:
        meta = yaml.safe_load(raw_meta) or {}
    except yaml.YAMLError as e:
        logger.error(f"[Skill] frontmatter YAML 解析失败 {path}: {e}")
        return None

    if not isinstance(meta, dict):
        logger.warning(f"[Skill] frontmatter 不是 dict: {path}")
        return None

    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        logger.warning(f"[Skill] 缺少 name: {path}")
        return None

    trigger_raw = meta.get("trigger", "manual")
    if trigger_raw not in ("keywords", "always", "manual"):
        logger.warning(
            f"[Skill] {name} 非法 trigger={trigger_raw}, 改为 manual"
        )
        trigger_raw = "manual"
    trigger: Trigger = trigger_raw  # type: ignore[assignment]

    keywords = _tuple_of_str(meta.get("keywords"))
    deps = SkillDependencies(
        mcp_servers=_tuple_of_str(meta.get("required_mcp_servers")),
        python=_tuple_of_str(meta.get("required_python")),
        brew=_tuple_of_str(meta.get("required_brew")),
        env=_tuple_of_str(meta.get("required_env")),
    )

    return Skill(
        name=name.strip(),
        description=str(meta.get("description", "")).strip(),
        trigger=trigger,
        keywords=keywords,
        body=body,
        path=path,
        enabled=bool(meta.get("enabled", True)),
        deps=deps,
    )


def _tuple_of_str(value) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(v).strip() for v in value if str(v).strip())
    return ()


def scan_skills(root: Path) -> list[Skill]:
    """递归扫描 skills/**/SKILL.md。重复 name 后者覆盖前者并警告。"""
    if not root.exists():
        return []

    skills: dict[str, Skill] = {}
    for md in root.rglob("SKILL.md"):
        try:
            text = md.read_text("utf-8")
        except OSError as e:
            logger.warning(f"[Skill] 读取失败 {md}: {e}")
            continue
        skill = parse_skill_md(text, md)
        if skill is None:
            continue
        if skill.name in skills:
            logger.warning(
                f"[Skill] 重名 {skill.name}，覆盖 {skills[skill.name].path} → {md}"
            )
        skills[skill.name] = skill

    return list(skills.values())
