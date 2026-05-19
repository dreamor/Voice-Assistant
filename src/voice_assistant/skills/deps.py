"""依赖解析器

职责：检查 skill 的 required_* 依赖；可选 auto-install pip 包。
不会自动跑 brew / npx（root 权限风险），只输出引导文本。
"""
import importlib
import logging
import os
import subprocess
import sys
from collections.abc import Iterable

from voice_assistant.skills.models import DependencyCheck, Skill

logger = logging.getLogger(__name__)


def _python_package_available(spec: str) -> bool:
    """spec 如 'requests' 或 'requests>=2.31'，只取包名做 import 判断"""
    pkg = spec.split(">")[0].split("=")[0].split("<")[0].split("!")[0].strip()
    if not pkg:
        return True
    # 替换 - 为 _ 以兼容 distribution 名（pip 包名 vs 模块名）
    candidates = {pkg, pkg.replace("-", "_")}
    for cand in candidates:
        try:
            importlib.import_module(cand)
            return True
        except ImportError:
            continue
    return False


def check_skill(
    skill: Skill, available_mcp_servers: Iterable[str]
) -> DependencyCheck:
    """逐项检查 skill 所需依赖"""
    avail_mcp = set(available_mcp_servers)
    missing_mcp = tuple(s for s in skill.deps.mcp_servers if s not in avail_mcp)
    missing_py = tuple(
        spec for spec in skill.deps.python if not _python_package_available(spec)
    )
    missing_brew: tuple[str, ...] = ()
    if sys.platform == "darwin":
        missing_brew = tuple(
            pkg for pkg in skill.deps.brew if not _brew_installed(pkg)
        )
    missing_env = tuple(name for name in skill.deps.env if not os.environ.get(name))
    return DependencyCheck(
        skill_name=skill.name,
        missing_mcp_servers=missing_mcp,
        missing_python=missing_py,
        missing_brew=missing_brew,
        missing_env=missing_env,
    )


def _brew_installed(pkg: str) -> bool:
    try:
        result = subprocess.run(
            ["brew", "list", "--formula", pkg],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def auto_install_python(specs: tuple[str, ...]) -> tuple[bool, str]:
    """运行 pip install 安装缺失的 python 包。

    Returns:
        (success, message)
    """
    if not specs:
        return True, "no-op"
    cmd = [sys.executable, "-m", "pip", "install", *specs]
    logger.info(f"[Skill] auto-install: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180
        )
    except subprocess.TimeoutExpired:
        return False, "pip install 超时（>180s）"
    except OSError as e:
        return False, f"pip 不可用: {e}"

    if result.returncode != 0:
        return False, f"pip install 失败: {result.stderr.strip()[:500]}"
    return True, f"已安装: {', '.join(specs)}"
