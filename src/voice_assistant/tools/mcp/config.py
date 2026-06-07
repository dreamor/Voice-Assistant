"""MCP server 配置加载"""
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

logger = logging.getLogger(__name__)

Transport = Literal["stdio", "sse", "http"]
_SECRET_RE = re.compile(r"\$\{secrets\.([\w\.\-]+)\}")


@dataclass(frozen=True)
class MCPServerConfig:
    id: str
    transport: Transport = "stdio"
    enabled: bool = True
    command: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    security_default: str = "write"  # read_only | write | dangerous


def _resolve_secrets(value: str, secrets: dict) -> str:
    """替换 ${secrets.path.to.key} 占位符。找不到时保留原串并记录警告。"""
    if not isinstance(value, str):
        return value

    def _sub(m: re.Match) -> str:
        path = m.group(1).split(".")
        node = secrets
        for p in path:
            if not isinstance(node, dict) or p not in node:
                logger.warning(f"[MCP] 未找到 secrets 占位符: {m.group(0)}")
                return m.group(0)
            node = node[p]
        return str(node)

    return _SECRET_RE.sub(_sub, value)


def _resolve_dict(d: dict, secrets: dict) -> dict:
    return {k: _resolve_secrets(v, secrets) for k, v in d.items()}


def load_secrets(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text("utf-8", errors="replace")) or {}
    except yaml.YAMLError as e:
        logger.error(f"[MCP] secrets 加载失败 {path}: {e}")
        return {}


def load_servers(path: Path, secrets_path: Path | None = None) -> list[MCPServerConfig]:
    if not path.exists():
        logger.info(f"[MCP] 配置文件不存在，跳过: {path}")
        return []

    raw = yaml.safe_load(path.read_text("utf-8", errors="replace")) or {}
    secrets = load_secrets(secrets_path) if secrets_path else {}

    servers: list[MCPServerConfig] = []
    for entry in raw.get("servers", []) or []:
        try:
            sid = entry["id"]
            transport = entry.get("transport", "stdio")
            cfg = MCPServerConfig(
                id=sid,
                transport=transport,
                enabled=entry.get("enabled", True),
                command=[_resolve_secrets(c, secrets) for c in entry.get("command", []) or []],
                env=_resolve_dict(entry.get("env", {}) or {}, secrets),
                url=_resolve_secrets(entry.get("url", ""), secrets),
                headers=_resolve_dict(entry.get("headers", {}) or {}, secrets),
                security_default=entry.get("security_default", "write"),
            )
            servers.append(cfg)
        except (KeyError, TypeError) as e:
            logger.error(f"[MCP] 无效的 server 条目，跳过: {entry} ({e})")

    return servers


def expand_env(env: dict[str, str]) -> dict[str, str]:
    """注入到子进程的 env：基于当前 os.environ + 覆盖项"""
    merged = dict(os.environ)
    merged.update(env)
    return merged
