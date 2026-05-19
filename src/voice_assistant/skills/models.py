"""Skill 数据模型"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Trigger = Literal["keywords", "always", "manual"]


@dataclass(frozen=True)
class SkillDependencies:
    mcp_servers: tuple[str, ...] = ()
    python: tuple[str, ...] = ()
    brew: tuple[str, ...] = ()
    env: tuple[str, ...] = ()


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    trigger: Trigger
    keywords: tuple[str, ...]
    body: str  # Markdown body (frontmatter 之外)
    path: Path
    enabled: bool = True
    deps: SkillDependencies = field(default_factory=SkillDependencies)

    def matches_keyword(self, text: str) -> bool:
        """大小写不敏感、子串匹配"""
        if self.trigger != "keywords" or not self.keywords:
            return False
        lower = text.lower()
        return any(k.lower() in lower for k in self.keywords)


@dataclass(frozen=True)
class DependencyCheck:
    """单个 skill 的依赖检查结果"""
    skill_name: str
    missing_mcp_servers: tuple[str, ...] = ()
    missing_python: tuple[str, ...] = ()
    missing_brew: tuple[str, ...] = ()
    missing_env: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not (
            self.missing_mcp_servers
            or self.missing_python
            or self.missing_brew
            or self.missing_env
        )

    def to_message(self) -> str:
        if self.ok:
            return f"[skill:{self.skill_name}] 依赖完整"
        lines = [f"[skill:{self.skill_name}] 缺失依赖:"]
        if self.missing_mcp_servers:
            lines.append(f"  MCP server: {', '.join(self.missing_mcp_servers)}")
        if self.missing_python:
            lines.append(f"  Python 包: {', '.join(self.missing_python)}")
            lines.append(
                f"    安装: pip install {' '.join(self.missing_python)}"
            )
        if self.missing_brew:
            lines.append(f"  Homebrew 包: {', '.join(self.missing_brew)}")
            lines.append(f"    安装: brew install {' '.join(self.missing_brew)}")
        if self.missing_env:
            lines.append(f"  环境变量: {', '.join(self.missing_env)}")
        return "\n".join(lines)
