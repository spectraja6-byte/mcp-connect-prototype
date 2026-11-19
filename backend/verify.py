"""Independent verification of MCP Connect's genuine MCP connectivity.

Checks, in order:
 1. /health returns HTTP 200
 2. /api/status reports a connected MCP session
 3. /api/tools discovers hello_mcp
 4. /api/invoke calls hello_mcp and returns a real greeting
 5. Direct MCP client connection (bypassing the REST bridge) to /mcp,
    to prove the bridge is not a shortcut around the protocol.

Run:  python3 backend/verify.py [bridge_base_url]

Configuration (no hardcoded ports):
  bridge base URL  argv[1], else $MCP_CONNECT_BASE_URL, else http://127.0.0.1:8000
  MCP server URL   $MCP_CONNECT_MCP_URL (same variable the bridge uses),
                   else http://127.0.0.1:8001/mcp
  access token     $MCP_CONNECT_API_TOKEN — sent as "Authorization: Bearer <token>"
                   to both the bridge and the MCP server. Must match the token
                   the backends were started with.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx
import httpx2  # client type the MCP SDK's streamable_http_client expects (installed with `mcp`)
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

BASE = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get("MCP_CONNECT_BASE_URL", "http://127.0.0.1:8000")
).rstrip("/")
MCP_URL = os.environ.get("MCP_CONNECT_MCP_URL", "http://127.0.0.1:8001/mcp")
TOKEN = os.environ.get("MCP_CONNECT_API_TOKEN", "").strip()
AUTH_HEADERS = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def result(ok: bool, detail: str) -> str:
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {detail}")
    return flag


async def main() -> int:
    flags: list[str] = []
    async with httpx.AsyncClient(base_url=BASE, timeout=15.0, headers=AUTH_HEADERS) as http:
        # 1. Health
        section("1. Health endpoint")
        try:
            r = await http.get("/health")
            flags.append(result(
                r.status_code == 200 and r.json().get("status") == "ok",
                f"GET /health -> {r.status_code} {r.text.strip()}",
            ))
        except Exception as exc:
            flags.append(result(False, f"health request failed: {exc}"))

        # 2. Status (MCP connection)
        section("2. MCP connection status (via REST bridge)")
        try:
            r = await http.get("/api/status")
            data = r.json()
            mcp = data.get("mcp", {})
            ok = (
                r.status_code == 200
                and mcp.get("connected") is True
                and bool(mcp.get("protocol_version"))
            )
            flags.append(result(ok, json.dumps(data, indent=2)))
        except Exception as exc:
            flags.append(result(False, f"status request failed: {exc}"))

        # 3. Tool discovery
        section("3. Tool discovery (via REST bridge)")
        try:
            r = await http.get("/api/tools")
            data = r.json()
            names = [t.get("name") for t in data.get("tools", [])]
            flags.append(result(
                r.status_code == 200 and "hello_mcp" in names,
                f"discovered tools: {names}",
            ))
        except Exception as exc:
            flags.append(result(False, f"tools request failed: {exc}"))

        # 4. Tool invocation
        section("4. Tool invocation — hello_mcp (via REST bridge)")
        try:
            r = await http.post("/api/invoke", json={
                "name": "hello_mcp",
                "arguments": {"name": "Verifier"},
            })
            data = r.json()
            text = ""
            for c in data.get("result", {}).get("content", []):
                if c.get("type") == "text":
                    text = c.get("text", "")
            flags.append(result(
                r.status_code == 200 and "Hello, Verifier" in text,
                f"response text: {text!r}",
            ))
        except Exception as exc:
            flags.append(result(False, f"invoke request failed: {exc}"))

    # 5. Direct MCP client — bypass the REST bridge entirely.
    #    Talk straight to the MCP server's /mcp endpoint.
    section(f"5. Direct MCP client over Streamable HTTP (bypassing bridge) -> {MCP_URL}")
    try:
        async with httpx2.AsyncClient(
            headers=AUTH_HEADERS, timeout=httpx2.Timeout(30.0, read=300.0)
        ) as mcp_http:
            async with streamable_http_client(MCP_URL, http_client=mcp_http) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    print(f"  initialized: protocol={init.protocol_version}, "
                          f"server={init.server_info.name} v{init.server_info.version}")
                    tools = (await session.list_tools()).tools
                    print(f"  tools: {[t.name for t in tools]}")
                    call = await session.call_tool("hello_mcp", {"name": "Direct"})
                    text = next(
                        (b.text for b in call.content if hasattr(b, "text")), ""
                    )
                    flags.append(result(
                        "hello_mcp" in [t.name for t in tools]
                        and "Hello, Direct" in text,
                        f"direct call response: {text!r}",
                    ))
    except Exception as exc:
        flags.append(result(False, f"direct MCP client failed: {exc}"))

    section("Summary")
    total = len(flags)
    passed = flags.count("PASS")
    print(f"{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
