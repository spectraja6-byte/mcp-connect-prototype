"""MCP Connect — REST bridge.

A thin HTTP layer the frontend talks to. Every tool discovery and invocation
goes through a *genuine* MCP client session (official MCP SDK, Streamable HTTP
transport) that connects to the separate MCP server process. Nothing is mocked.

The bridge also serves the built frontend's static files so that the browser
and the API share a single origin — no cross-port proxy needed in production.

Endpoints:
  GET  /health        — liveness, HTTP 200
  GET  /api/status    — server info + live MCP connection check
  GET  /api/tools     — discover MCP tools via tools/list
  POST /api/invoke    — invoke an MCP tool via tools/call
  GET  /assets/*      — built JS/CSS assets
  GET  /              — index.html (SPA fallback for non-API routes)
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_server import server as mcp_server

# The MCP server runs as a separate process on its own port. Default 8001.
MCP_URL = os.environ.get("MCP_CONNECT_MCP_URL", "http://127.0.0.1:8001/mcp")
STARTED_AT = time.time()

# Path to the built frontend (Vite outputs to ../dist relative to backend/).
DIST_DIR = Path(os.environ.get("MCP_CONNECT_DIST_DIR", Path(__file__).resolve().parent.parent / "dist"))

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _json(body: Any, status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=CORS)


async def _mcp_call(fn: Callable[[ClientSession], Awaitable[Any]]) -> Any:
    """Open a real MCP client session over Streamable HTTP and run fn(session)."""
    async with streamable_http_client(MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


async def health(_: Request) -> Response:
    return _json({"status": "ok"})


async def api_status(_: Request) -> Response:
    info: dict[str, Any] = {
        "project": "MCP Connect",
        "server_name": mcp_server.name,
        "server_version": mcp_server.version,
        "mcp_url": MCP_URL,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
    }
    try:
        async def probe(session: ClientSession):
            init = await session.initialize()
            caps = init.capabilities.model_dump(exclude_none=True) or {}
            return {
                "connected": True,
                "protocol_version": str(init.protocol_version),
                "server_info": {
                    "name": init.server_info.name,
                    "version": init.server_info.version,
                },
                "capabilities": list(caps.keys()),
            }
        info["mcp"] = await _mcp_call(probe)
        info["status"] = "connected"
    except Exception as exc:  # noqa: BLE001 — surface any connection failure
        info["mcp"] = {"connected": False, "error": str(exc)}
        info["status"] = "disconnected"
    return _json(info)


async def api_tools(_: Request) -> Response:
    try:
        async def discover(session: ClientSession):
            result = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in result.tools
            ]
        tools = await _mcp_call(discover)
        return _json({"ok": True, "tools": tools})
    except Exception as exc:  # noqa: BLE001
        return _json({"ok": False, "error": str(exc), "tools": []}, status=502)


async def api_invoke(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        return _json({"ok": False, "error": "Invalid JSON body"}, status=400)

    name = payload.get("name")
    arguments = payload.get("arguments") or {}
    if not name:
        return _json({"ok": False, "error": "Missing 'name' field"}, status=400)

    try:
        async def call(session: ClientSession):
            result = await session.call_tool(name, arguments)
            content = []
            for block in result.content:
                if hasattr(block, "text"):
                    content.append({"type": "text", "text": block.text})
                else:
                    content.append({"type": str(getattr(block, "type", "unknown"))})
            return {
                "isError": bool(getattr(result, "isError", False)),
                "content": content,
            }
        out = await _mcp_call(call)
        return _json({"ok": True, "result": out})
    except Exception as exc:  # noqa: BLE001
        return _json({"ok": False, "error": str(exc)}, status=502)


async def cors_preflight(_: Request) -> Response:
    return Response("", headers=CORS)


async def spa_fallback(request: Request) -> Response:
    """Serve index.html for any non-API GET request (SPA routing)."""
    index = DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return _json({"ok": False, "error": "Frontend build not found. Run: npm run build"}, status=404)


# Build the route list. API routes take priority, then static assets, then SPA fallback.
routes: list[Any] = [
    Route("/health", health, methods=["GET"]),
    Route("/api/status", api_status, methods=["GET"]),
    Route("/api/tools", api_tools, methods=["GET"]),
    Route("/api/invoke", api_invoke, methods=["POST"]),
    Route("/{path:path}", cors_preflight, methods=["OPTIONS"]),
]

# Mount static assets if the dist directory exists.
if DIST_DIR.exists():
    routes.append(Mount("/assets", app=StaticFiles(directory=str(DIST_DIR / "assets")), name="assets"))
    routes.append(Route("/", spa_fallback, methods=["GET"]))
    routes.append(Route("/{path:path}", spa_fallback, methods=["GET"]))

app = Starlette(routes=routes)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.environ.get("MCP_CONNECT_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_CONNECT_PORT", "8000")),
        reload=False,
    )
