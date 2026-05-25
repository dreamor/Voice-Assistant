"""
AppLifecycle - 应用生命周期管理

替代 session.py 中的模块级全局变量，统一管理 MCPManager、SkillManager
和 ToolRegistry 的生命周期。
"""
import logging
from pathlib import Path

from voice_assistant.config import config

logger = logging.getLogger(__name__)


class AppLifecycle:
    """应用生命周期管理器

    拥有 MCPManager、SkillManager 和 ToolRegistry 实例，
    提供统一的初始化和关闭接口。
    """

    def __init__(self):
        self._mcp_manager = None
        self._skill_manager = None
        self._tool_registry = None

    @property
    def mcp_manager(self):
        return self._mcp_manager

    @property
    def skill_manager(self):
        return self._skill_manager

    @property
    def tool_registry(self):
        return self._tool_registry

    def build_tool_registry(self):
        """根据配置构建 ToolRegistry 并启动 MCP/Skill"""
        if self._tool_registry is not None:
            return self._tool_registry

        from voice_assistant.platform import detect_platform
        from voice_assistant.security.safe_guard import SafeGuard, SecurityLevel, ToolPolicy
        from voice_assistant.tools.platform_specific import get_platform_tools
        from voice_assistant.tools.registry import ToolRegistry
        from voice_assistant.tools.universal import get_universal_tools

        guard = SafeGuard(
            policies=[
                ToolPolicy(tool_name=name, blocked=True)
                for name in config.tools.blocked
            ]
            + [
                ToolPolicy(
                    tool_name=ov.name,
                    override_level=SecurityLevel(ov.level),
                )
                for ov in config.tools.overrides
            ]
        )
        platform = detect_platform()
        registry = ToolRegistry(current_platform=platform, safe_guard=guard)
        registry.register_all(get_universal_tools())
        registry.register_all(get_platform_tools(platform))

        # 在 MCP server 启动前先注册 meta tools
        from voice_assistant.tools.mcp import get_mcp_meta_tools
        registry.register_all(get_mcp_meta_tools())

        self._start_mcp(registry)

        # Skill 系统
        from voice_assistant.skills.meta_tools import get_skill_meta_tools
        registry.register_all(get_skill_meta_tools())
        self._start_skills()

        self._tool_registry = registry
        logger.info(
            f"[AppLifecycle] 注册 {len(registry.list_tools())} 个工具 (platform={platform})"
        )
        return registry

    def _start_mcp(self, registry) -> None:
        """启动 MCP server 并把工具桥接到 registry"""
        if self._mcp_manager is not None:
            return
        try:
            from voice_assistant.tools.mcp import MCPManager, load_servers

            cfg_dir = Path("config")
            servers = load_servers(
                cfg_dir / "mcp_servers.yaml",
                secrets_path=cfg_dir / "secrets.yaml",
            )
            if not servers:
                return
            mgr = MCPManager(registry)
            mgr.start(servers)
            self._mcp_manager = mgr
        except Exception:
            logger.exception("[AppLifecycle] MCP 启动失败，已忽略")

    def _start_skills(self) -> None:
        """加载 skills/ 目录下的 SKILL.md"""
        if self._skill_manager is not None:
            return
        try:
            from voice_assistant.skills import SkillManager

            root = Path("skills")
            mgr = SkillManager(root)
            mgr.reload()
            self._skill_manager = mgr
        except Exception:
            logger.exception("[AppLifecycle] Skill 加载失败，已忽略")

    def build_skill_addendum(self, user_text: str) -> str:
        """每次 LLM 调用前生成 system prompt 补丁"""
        if self._skill_manager is None:
            return ""
        try:
            return self._skill_manager.build_addendum_for_message(user_text)
        except Exception:
            logger.exception("[AppLifecycle] build_skill_addendum 失败")
            return ""

    def shutdown(self) -> None:
        """关闭所有资源"""
        if self._mcp_manager is not None:
            try:
                self._mcp_manager.shutdown()
            except Exception:
                logger.exception("[AppLifecycle] MCP 关闭失败")
            finally:
                self._mcp_manager = None

        self._skill_manager = None
        self._tool_registry = None


# 全局单例
_lifecycle: AppLifecycle | None = None


def get_lifecycle() -> AppLifecycle:
    """获取全局 AppLifecycle 实例（懒初始化）"""
    global _lifecycle
    if _lifecycle is None:
        _lifecycle = AppLifecycle()
    return _lifecycle


def shutdown_lifecycle() -> None:
    """关闭全局 AppLifecycle"""
    global _lifecycle
    if _lifecycle is not None:
        _lifecycle.shutdown()
        _lifecycle = None
