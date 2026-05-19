"""Skill selector + system prompt builder

策略：
- always: 全文注入到 system prompt
- keywords: 命中时把 SKILL.md body 注入到当前用户消息之前
- manual: 用户显式触发（例如 /skill <name>）
"""
import logging
from collections.abc import Iterable

from voice_assistant.skills.models import Skill

logger = logging.getLogger(__name__)


def select_for_message(
    skills: Iterable[Skill], user_message: str
) -> list[Skill]:
    """根据用户消息挑出应触发的 skill（不包含 always — 那个走 system prompt）"""
    out: list[Skill] = []
    for s in skills:
        if not s.enabled:
            continue
        if s.matches_keyword(user_message):
            out.append(s)
    return out


def build_system_prompt_addendum(skills: Iterable[Skill]) -> str:
    """构造给 LLM 的额外 system 提示

    - always skill：完整 body 拼入
    - 其他可用 skill：只列名 + description（让 LLM 知道有哪些能力）
    """
    enabled = [s for s in skills if s.enabled]
    if not enabled:
        return ""

    parts: list[str] = []

    always_skills = [s for s in enabled if s.trigger == "always"]
    if always_skills:
        parts.append("## 始终启用的 Skill\n")
        for s in always_skills:
            parts.append(f"### {s.name}\n{s.body}\n")

    other_skills = [s for s in enabled if s.trigger != "always"]
    if other_skills:
        parts.append("## 可用 Skill（按需触发）")
        for s in other_skills:
            trig = (
                f"keywords={list(s.keywords)}" if s.trigger == "keywords"
                else "manual"
            )
            parts.append(f"- **{s.name}** ({trig}): {s.description}")

    return "\n".join(parts).strip()


def build_addendum_for_message(
    skills: Iterable[Skill], user_message: str
) -> str:
    """组合 always-skill prompt + 命中 keyword 的 skill body

    输出格式：
        ## 始终启用的 Skill
        ### name
        body
        ...

        ## 触发的 Skill（基于用户消息）
        ### name
        body

    用于 VoiceSession 在每次 LLM 调用前注入 system prompt 末尾。
    """
    enabled = [s for s in skills if s.enabled]
    if not enabled:
        return ""

    parts: list[str] = []

    always = [s for s in enabled if s.trigger == "always"]
    if always:
        parts.append("## 始终启用的 Skill")
        for s in always:
            parts.append(f"### {s.name}\n{s.body}")

    hit = [
        s for s in enabled
        if s.trigger == "keywords" and s.matches_keyword(user_message)
    ]
    if hit:
        parts.append("## 触发的 Skill（基于用户消息）")
        for s in hit:
            parts.append(f"### {s.name}\n{s.body}")

    return "\n\n".join(parts).strip()
