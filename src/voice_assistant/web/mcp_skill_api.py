"""MCP/Skill 管理 API 路由"""
import logging

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["mcp_skill"])


@router.get("/mcp/servers")
async def list_mcp_servers_api():
    """列出当前所有 MCP server"""
    from voice_assistant.core.session import get_mcp_manager

    mgr = get_mcp_manager()
    if mgr is None:
        return {"servers": []}
    return {"servers": mgr.list_servers()}


@router.get("/skills")
async def list_skills_api():
    """列出所有 skill 及启停状态、依赖摘要"""
    from voice_assistant.core.session import get_mcp_manager, get_skill_manager

    skill_mgr = get_skill_manager()
    if skill_mgr is None:
        return {"skills": []}

    mcp_mgr = get_mcp_manager()
    available_mcp = (
        [s["id"] for s in mcp_mgr.list_servers()] if mcp_mgr else []
    )
    checks_by_name = {
        c.skill_name: c for c in skill_mgr.check_dependencies(available_mcp)
    }

    out = []
    for s in skill_mgr.list_skills():
        check = checks_by_name.get(s.name)
        out.append({
            "name": s.name,
            "description": s.description,
            "trigger": s.trigger,
            "keywords": list(s.keywords),
            "enabled": s.enabled,
            "deps": {
                "mcp_servers": list(s.deps.mcp_servers),
                "python": list(s.deps.python),
                "brew": list(s.deps.brew),
                "env": list(s.deps.env),
            },
            "deps_ok": check.ok if check else True,
            "deps_missing": (
                {
                    "mcp_servers": list(check.missing_mcp_servers),
                    "python": list(check.missing_python),
                    "brew": list(check.missing_brew),
                    "env": list(check.missing_env),
                }
                if check and not check.ok else None
            ),
        })
    return {"skills": out}


@router.post("/skills/{name}/enable")
async def enable_skill_api(name: str):
    """启用 skill（仅运行时，不写回磁盘）"""
    from voice_assistant.core.session import get_skill_manager

    mgr = get_skill_manager()
    if mgr is None:
        raise HTTPException(status_code=503, detail="Skill 系统未启用")
    if not mgr.set_enabled(name, True):
        raise HTTPException(status_code=404, detail=f"未找到 skill: {name}")
    return {"success": True, "name": name, "enabled": True}


@router.post("/skills/{name}/disable")
async def disable_skill_api(name: str):
    """禁用 skill（仅运行时）"""
    from voice_assistant.core.session import get_skill_manager

    mgr = get_skill_manager()
    if mgr is None:
        raise HTTPException(status_code=503, detail="Skill 系统未启用")
    if not mgr.set_enabled(name, False):
        raise HTTPException(status_code=404, detail=f"未找到 skill: {name}")
    return {"success": True, "name": name, "enabled": False}


@router.post("/skills/reload")
async def reload_skills_api():
    """重新扫描 skills/ 目录"""
    from voice_assistant.core.session import get_skill_manager

    mgr = get_skill_manager()
    if mgr is None:
        raise HTTPException(status_code=503, detail="Skill 系统未启用")
    count = mgr.reload()
    return {"success": True, "count": count}
