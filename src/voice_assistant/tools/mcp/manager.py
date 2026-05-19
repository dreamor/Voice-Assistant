"""MCP 客户端管理器

职责：
- 在后台线程独占的 asyncio loop 中启动/维持 MCP server 连接
- 列出每个 server 的工具并通过 bridge 注册到 ToolRegistry
- 同步关闭

MVP：只支持 stdio transport。SSE / Streamable HTTP 在后续阶段扩展。
"""
import asyncio
import logging
import sys
import threading
from typing import TYPE_CHECKING

from voice_assistant.tools.mcp.bridge import make_tool_definition
from voice_assistant.tools.mcp.config import MCPServerConfig, expand_env

if TYPE_CHECKING:
    from voice_assistant.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class _ServerHandle:
    """单个 server 的长驻 task 状态"""

    def __init__(self, server: MCPServerConfig):
        self.server = server
        self.task: asyncio.Task | None = None
        self.ready: asyncio.Event = asyncio.Event()
        self.stop: asyncio.Event = asyncio.Event()
        self.session: object | None = None
        self.tool_names: list[str] = []
        self.error: BaseException | None = None


class MCPManager:
    """同步外观，内部维持一个独立的 asyncio 事件循环线程。

    生命周期:
        manager = MCPManager(registry)
        manager.start(servers)        # 启动连接 + 注册工具（阻塞至 ready 或超时）
        ...
        manager.shutdown()            # 关闭所有 server 与 loop
    """

    def __init__(self, registry: "ToolRegistry"):
        self._registry = registry
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._handles: dict[str, _ServerHandle] = {}
        self._ready = threading.Event()

    # ----- 公共 API -----

    def start(self, servers: list[MCPServerConfig]) -> None:
        if not servers:
            logger.info("[MCP] 无 server 配置，跳过启动")
            return

        self._thread = threading.Thread(
            target=self._loop_runner, name="mcp-loop", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=5)
        if self._loop is None:
            logger.error("[MCP] 事件循环未启动")
            return

        for server in servers:
            if not server.enabled:
                logger.info(f"[MCP] 跳过禁用的 server: {server.id}")
                continue
            handle = _ServerHandle(server)
            self._handles[server.id] = handle
            asyncio.run_coroutine_threadsafe(
                self._spawn_server_task(handle), self._loop
            )

        # 等所有 server ready (或失败)
        deadline = 30
        for handle in self._handles.values():
            fut = asyncio.run_coroutine_threadsafe(
                _wait_event(handle.ready, deadline), self._loop
            )
            try:
                fut.result(timeout=deadline + 2)
            except Exception:
                logger.exception(f"[MCP] 等待 {handle.server.id} ready 失败")

    def list_servers(self) -> list[dict]:
        """返回每个 server 的运行态摘要（供 LLM / Web UI 反射用）"""
        out = []
        for sid, h in self._handles.items():
            out.append({
                "id": sid,
                "transport": h.server.transport,
                "enabled": h.server.enabled,
                "ready": h.ready.is_set() and h.error is None,
                "error": str(h.error) if h.error else None,
                "tools": list(h.tool_names),
            })
        return out

    def shutdown(self) -> None:
        if self._loop is None:
            return

        async def _signal_all() -> None:
            for h in self._handles.values():
                h.stop.set()

        try:
            asyncio.run_coroutine_threadsafe(_signal_all(), self._loop).result(timeout=5)
            # 等所有 task 结束
            tasks = [h.task for h in self._handles.values() if h.task]
            if tasks:
                async def _gather() -> None:
                    await asyncio.gather(*tasks, return_exceptions=True)

                asyncio.run_coroutine_threadsafe(_gather(), self._loop).result(timeout=10)
        except Exception:
            logger.exception("[MCP] 关闭 server 任务失败")
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=5)
            self._loop = None
            self._thread = None
            self._handles.clear()

    # ----- 内部 -----

    def _loop_runner(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            loop.close()

    async def _spawn_server_task(self, handle: _ServerHandle) -> None:
        handle.task = asyncio.create_task(
            self._run_server(handle), name=f"mcp-server-{handle.server.id}"
        )

    async def _run_server(self, handle: _ServerHandle) -> None:
        """单 task 内完整管理 server 生命周期 — 满足 anyio cancel scope 同 task 约束。"""
        server = handle.server
        try:
            if server.transport == "stdio":
                await self._run_stdio(handle)
            elif server.transport == "sse":
                await self._run_sse(handle)
            elif server.transport == "http":
                await self._run_http(handle)
            else:
                logger.error(f"[MCP] {server.id}: 未知 transport={server.transport}")
                handle.ready.set()
        except Exception as e:
            handle.error = e
            logger.exception(f"[MCP] {server.id} 运行失败")
        finally:
            handle.ready.set()  # 确保等待方不会卡住

    async def _run_stdio(self, handle: _ServerHandle) -> None:
        server = handle.server
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        if not server.command:
            logger.error(f"[MCP] {server.id}: stdio 需要 command")
            handle.ready.set()
            return

        cmd = server.command[0]
        if cmd in ("python", "python3"):
            cmd = sys.executable

        params = StdioServerParameters(
            command=cmd,
            args=server.command[1:],
            env=expand_env(server.env),
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await self._register_and_wait(handle, session)

    async def _run_sse(self, handle: _ServerHandle) -> None:
        server = handle.server
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        if not server.url:
            logger.error(f"[MCP] {server.id}: sse 需要 url")
            handle.ready.set()
            return

        async with sse_client(server.url, headers=server.headers or None) as (read, write):
            async with ClientSession(read, write) as session:
                await self._register_and_wait(handle, session)

    async def _run_http(self, handle: _ServerHandle) -> None:
        server = handle.server
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        if not server.url:
            logger.error(f"[MCP] {server.id}: http 需要 url")
            handle.ready.set()
            return

        async with streamablehttp_client(
            server.url, headers=server.headers or None
        ) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await self._register_and_wait(handle, session)

    async def _register_and_wait(self, handle: _ServerHandle, session) -> None:
        """初始化 session、注册工具、阻塞直到 shutdown"""
        server = handle.server
        await session.initialize()
        tools_result = await session.list_tools()
        assert self._loop is not None
        count = 0
        for tool in tools_result.tools:
            td = make_tool_definition(
                server_id=server.id,
                mcp_tool_name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema
                or {"type": "object", "properties": {}},
                call_tool=session.call_tool,
                loop=self._loop,
                security_default=server.security_default,
            )
            self._registry.register(td)
            handle.tool_names.append(td.name)
            count += 1
        handle.session = session
        logger.info(
            f"[MCP] 已连接 {server.transport} server={server.id}, 注册 {count} 个工具"
        )
        handle.ready.set()
        await handle.stop.wait()


async def _wait_event(event: asyncio.Event, timeout: float) -> None:
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except TimeoutError:
        logger.warning(f"[MCP] 等待 event 超时 {timeout}s")
