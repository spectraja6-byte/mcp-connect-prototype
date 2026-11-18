"""Run the MCP server standalone on its own port (Streamable HTTP at /mcp)."""
from __future__ import annotations

import os

import uvicorn

from mcp_server import server as mcp_server

app = mcp_server.streamable_http_app(streamable_http_path="/mcp")

if __name__ == "__main__":
    uvicorn.run(
        "run_mcp:app",
        host=os.environ.get("MCP_SERVER_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCP_SERVER_PORT", "8001")),
        reload=False,
    )
