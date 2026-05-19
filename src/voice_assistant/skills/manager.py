"""SkillManager — 加载 + 启停 + 查询的统一外观"""
import logging
from collections.abc import Iterable
from pathlib import Path

from voice_assistant.skills.deps import check_skill
from voice_assistant.skills.loader import scan_skills
from voice_assistant.skills.models import DependencyCheck, Skill
from voice_assistant.skills.selector import (
    build_addendum_for_message,
    build_system_prompt_addendum,
    select_for_message,
)

logger = logging.getLogger(__name__)


class SkillManager:
    """同步外观，加载 skills 后可被 session 查询。"""

    def __init__(self, root: Path):
        self._root = root
        self._skills: dict[str, Skill] = {}

    def reload(self) -> int:
        """从磁盘重新加载，返回 skill 数"""
        skills = scan_skills(self._root)
        self._skills = {s.name: s for s in skills}
        logger.info(f"[SkillManager] 加载 {len(self._skills)} 个 skill")
        return len(self._skills)

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """运行时启停（不写回磁盘）。frozen dataclass → 重建实例。"""
        from dataclasses import replace

        s = self._skills.get(name)
        if s is None:
            return False
        self._skills[name] = replace(s, enabled=enabled)
        return True

    def check_dependencies(
        self, available_mcp_servers: Iterable[str]
    ) -> list[DependencyCheck]:
        """对所有 enabled skill 跑依赖检查"""
        avail = list(available_mcp_servers)
        return [
            check_skill(s, avail) for s in self._skills.values() if s.enabled
        ]

    def select_for_message(self, user_message: str) -> list[Skill]:
        return select_for_message(self._skills.values(), user_message)

    def build_system_prompt_addendum(self) -> str:
        return build_system_prompt_addendum(self._skills.values())

    def build_addendum_for_message(self, user_message: str) -> str:
        """每次 LLM 调用前注入：always skill + 命中关键词的 skill"""
        return build_addendum_for_message(self._skills.values(), user_message)
