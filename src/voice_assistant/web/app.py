"""FastAPI 应用工厂、生命周期与路由注册"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from voice_assistant.core.lifecycle import get_lifecycle, shutdown_lifecycle
from voice_assistant.db import init_db
from voice_assistant.web.config_api import router as config_router
from voice_assistant.web.history_api import router as history_router
from voice_assistant.web.mcp_skill_api import router as mcp_skill_router
from voice_assistant.web.providers_api import router as providers_router
from voice_assistant.web.routes import STATIC_DIR
from voice_assistant.web.routes import router as static_router
from voice_assistant.web.ws import cleanup_session, sessions

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_db()
    logger.info("[WebUI] 服务启动")

    # 启动时主动初始化 MCP/Skill manager
    try:
        get_lifecycle().build_tool_registry()
    except Exception:
        logger.exception("[WebUI] 启动时构建 ToolRegistry 失败（MCP/Skill 不可用）")

    yield

    # 清理所有会话
    for client_id in list(sessions.keys()):
        cleanup_session(client_id)
    # 关闭 MCP server 子进程 / 连接
    try:
        shutdown_lifecycle()
    except Exception:
        logger.exception("[WebUI] MCP 关闭失败")
    logger.info("[WebUI] 服务关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    app = FastAPI(
        title="Voice Assistant Web UI",
        description="语音助手 Web 界面",
        version="2.2.0",
        lifespan=lifespan,
    )

    # 注册路由
    app.include_router(static_router)
    app.include_router(config_router)
    app.include_router(providers_router)
    app.include_router(history_router)
    app.include_router(mcp_skill_router)

    # WebSocket 端点
    from voice_assistant.web.ws import websocket_endpoint
    app.websocket("/ws/{client_id}")(websocket_endpoint)

    # 静态文件服务
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
