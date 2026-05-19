"""Skill 反射工具（只读 + 启停开关）

只读 + READ_ONLY 不需要二次确认，符合「用户语音问问情况 / 启停」场景。
"""
from voice_assistant.security.safe_guard import SecurityLevel
from voice_assistant.tools.registry import ToolDefinition


def _get_manager():
    from voice_assistant.core.session import get_skill_manager

    return get_skill_manager()


def _list_skills() -> str:
    mgr = _get_manager()
    if mgr is None:
        return "Skill 系统未启用"
    skills = mgr.list_skills()
    if not skills:
        return "暂无 skill"

    lines = []
    for s in skills:
        flag = "✓" if s.enabled else "✗"
        lines.append(
            f"{flag} {s.name} [{s.trigger}]: {s.description}"
        )
    return "Skills:\n" + "\n".join(lines)


def _check_skill_deps(name: str) -> str:
    mgr = _get_manager()
    if mgr is None:
        return "Skill 系统未启用"
    skill = mgr.get(name)
    if skill is None:
        return f"未找到 skill: {name}"

    from voice_assistant.core.session import get_mcp_manager

    mcp_mgr = get_mcp_manager()
    mcp_ids = (
        [s["id"] for s in mcp_mgr.list_servers()] if mcp_mgr else []
    )
    check = mgr.check_dependencies(mcp_ids)
    for c in check:
        if c.skill_name == name:
            return c.to_message()
    return f"未找到依赖检查结果: {name}"


def _enable_skill(name: str) -> str:
    mgr = _get_manager()
    if mgr is None:
        return "Skill 系统未启用"
    if mgr.set_enabled(name, True):
        return f"已启用 skill: {name}"
    return f"未找到 skill: {name}"


def _disable_skill(name: str) -> str:
    mgr = _get_manager()
    if mgr is None:
        return "Skill 系统未启用"
    if mgr.set_enabled(name, False):
        return f"已禁用 skill: {name}"
    return f"未找到 skill: {name}"


def get_skill_meta_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="list_skills",
            description="列出所有已加载的 skill 及其启停状态。用户问『有哪些 skill / 技能包』时调用。",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_list_skills,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="check_skill_deps",
            description="检查指定 skill 的依赖是否齐全（MCP server / Python 包 / brew / 环境变量）。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "skill 名"}
                },
                "required": ["name"],
            },
            handler=_check_skill_deps,
            security_level=SecurityLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="enable_skill",
            description="启用一个 skill（仅运行时生效，不写回磁盘）。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "skill 名"}
                },
                "required": ["name"],
            },
            handler=_enable_skill,
            security_level=SecurityLevel.WRITE,
        ),
        ToolDefinition(
            name="disable_skill",
            description="禁用一个 skill（仅运行时生效，不写回磁盘）。",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "skill 名"}
                },
                "required": ["name"],
            },
            handler=_disable_skill,
            security_level=SecurityLevel.WRITE,
        ),
    ]
