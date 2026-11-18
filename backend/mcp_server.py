"""MCP Connect — MCP server definition.

Defines the MCP server and its tools using the official MCP SDK (v2).
The hello_mcp tool accepts a name and returns a greeting.
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

server = MCPServer(
    name="mcp-connect",
    version="0.1.0",
    title="MCP Connect",
    description="Connectivity and controlled execution layer for AI agents.",
)


@server.tool(name="hello_mcp", description="Accept a name and return a greeting.")
async def hello_mcp(name: str) -> str:
    """Return a greeting for the given name."""
    cleaned = (name or "").strip() or "world"
    return f"Hello, {cleaned}! MCP Connect is online."
