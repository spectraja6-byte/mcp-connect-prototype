"""Authentication tests for MCP Connect (bearer token on bridge and MCP server).

Self-contained: starts its own throwaway backend pairs on separate ports, so it
never touches a running instance, and needs nothing beyond requirements.txt.

Scenarios:
  A. token configured  — authorised / missing / invalid credentials, REST bridge
                         and direct MCP access, CORS preflight, public paths
  B. token not set     — protected paths fail closed (503), even with a header
  C. token too short   — both processes refuse to start

Run:  python3 backend/test_auth.py
Env:  MCP_CONNECT_TEST_PORT  base port (default 18000; uses base and base+1)
"""
from __future__ import annotations

import asyncio
import os
import secrets
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import httpx2  # client type the MCP SDK's streamable_http_client expects (installed with `mcp`)
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

HERE = Path(__file__).resolve().parent
BASE_PORT = int(os.environ.get("MCP_CONNECT_TEST_PORT", "18000"))
BRIDGE_PORT, MCP_PORT = BASE_PORT, BASE_PORT + 1
BRIDGE = f"http://127.0.0.1:{BRIDGE_PORT}"
MCP = f"http://127.0.0.1:{MCP_PORT}/mcp"
TRUSTED_ORIGIN = "http://trusted.example"
OTHER_ORIGIN = "http://untrusted.example"

INIT_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "auth-test", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

flags: list[str] = []
bodies: list[str] = []  # every response body seen, to prove the token never leaks


def check(ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {detail}")
    flags.append("PASS" if ok else "FAIL")


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _env(extra: dict[str, str]) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("MCP_CONNECT_", "MCP_SERVER_"))
    }
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "MCP_SERVER_PORT": str(MCP_PORT),
            "MCP_CONNECT_PORT": str(BRIDGE_PORT),
            "MCP_CONNECT_MCP_URL": MCP,
        }
    )
    env.update(extra)
    return env


def _listening(port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while True:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            if time.time() >= deadline:
                return False
            time.sleep(0.2)


@contextmanager
def backends(extra_env: dict[str, str]):
    for port in (BRIDGE_PORT, MCP_PORT):
        if _listening(port, 0.0):
            raise RuntimeError(f"port {port} is already in use; set MCP_CONNECT_TEST_PORT")
    procs = [
        subprocess.Popen(
            [sys.executable, script],
            cwd=HERE,
            env=_env(extra_env),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for script in ("run_mcp.py", "app.py")
    ]
    try:
        if not (_listening(MCP_PORT, 20) and _listening(BRIDGE_PORT, 20)):
            raise RuntimeError("test backends did not start")
        yield
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def get(c: httpx.Client, method: str, path: str, **kw) -> httpx.Response:
    r = c.request(method, path, **kw)
    bodies.append(r.text)
    return r


async def mcp_call(token: str | None) -> tuple[bool, str]:
    headers = bearer(token) if token else {}
    try:
        async def run() -> str:
            async with httpx2.AsyncClient(
                headers=headers, timeout=httpx2.Timeout(15.0, read=30.0)
            ) as http_client:
                async with streamable_http_client(MCP, http_client=http_client) as (r, w):
                    async with ClientSession(r, w) as session:
                        await session.initialize()
                        res = await session.call_tool("hello_mcp", {"name": "Direct"})
                        return next((b.text for b in res.content if hasattr(b, "text")), "")

        text = await asyncio.wait_for(run(), timeout=30)
        return "Hello, Direct" in text, text
    except Exception as exc:  # noqa: BLE001 — any failure means "not connected"
        return False, type(exc).__name__


def scenario_token_set() -> None:
    section("A. Token configured (bridge + MCP server both enforce it)")
    token = secrets.token_hex(16)
    env = {"MCP_CONNECT_API_TOKEN": token, "MCP_CONNECT_CORS_ORIGINS": TRUSTED_ORIGIN}
    with backends(env), httpx.Client(base_url=BRIDGE, timeout=20.0) as c:
        r = get(c, "GET", "/health")
        check(r.status_code == 200, f"GET /health without token -> {r.status_code} (public)")

        invoke_body = {"name": "hello_mcp", "arguments": {"name": "Intruder"}}
        endpoints = [
            ("GET", "/api/status", {}),
            ("GET", "/api/tools", {}),
            ("POST", "/api/invoke", {"json": invoke_body}),
        ]
        for method, path, kw in endpoints:
            r = get(c, method, path, **kw)
            check(
                r.status_code == 401 and r.headers.get("www-authenticate") == "Bearer",
                f"{method} {path} with no credentials -> {r.status_code}, WWW-Authenticate={r.headers.get('www-authenticate')!r}",
            )
        for method, path, kw in endpoints:
            r = get(c, method, path, headers=bearer("x" * 32), **kw)
            check(r.status_code == 401, f"{method} {path} with wrong token -> {r.status_code}")

        r = get(c, "POST", "/api/invoke", json=invoke_body)
        check("Intruder" not in r.text and "result" not in r.json(), "unauthenticated /api/invoke executed nothing")

        malformed = {
            "wrong scheme (Basic)": f"Basic {token}",
            "scheme without credential": "Bearer",
            "token without scheme": token,
            "token with extra character": f"Bearer {token}x",
            "token missing last character": f"Bearer {token[:-1]}",
        }
        for label, value in malformed.items():
            r = get(c, "GET", "/api/tools", headers={"Authorization": value})
            check(r.status_code == 401, f"malformed header [{label}] -> {r.status_code}")

        r = get(c, "GET", "/api/status", headers=bearer(token))
        data = r.json() if r.status_code == 200 else {}
        check(
            r.status_code == 200 and data.get("mcp", {}).get("connected") is True,
            f"GET /api/status with valid token -> {r.status_code}, mcp.connected={data.get('mcp', {}).get('connected')}",
        )
        r = get(c, "GET", "/api/tools", headers=bearer(token))
        names = [t.get("name") for t in r.json().get("tools", [])] if r.status_code == 200 else []
        check("hello_mcp" in names, f"GET /api/tools with valid token -> {r.status_code}, tools={names}")
        r = get(c, "POST", "/api/invoke", headers=bearer(token), json={"name": "hello_mcp", "arguments": {"name": "Tester"}})
        text = "".join(b.get("text", "") for b in r.json().get("result", {}).get("content", [])) if r.status_code == 200 else ""
        check("Hello, Tester" in text, f"POST /api/invoke with valid token -> {r.status_code}, {text!r}")
        r = get(c, "GET", "/api/tools", headers={"Authorization": f"bearer {token}"})
        check(r.status_code == 200, f"lowercase 'bearer' scheme accepted -> {r.status_code}")

        # MCP server enforces auth on its own, independent of the bridge.
        r = get(httpx.Client(timeout=20.0), "POST", MCP, headers=MCP_HEADERS, json=INIT_BODY)
        check(r.status_code == 401, f"direct POST {MCP} with no credentials -> {r.status_code}")
        r = get(httpx.Client(timeout=20.0), "POST", MCP, headers={**MCP_HEADERS, **bearer("y" * 32)}, json=INIT_BODY)
        check(r.status_code == 401, f"direct POST {MCP} with wrong token -> {r.status_code}")
        ok, detail = asyncio.run(mcp_call(None))
        check(not ok, f"MCP SDK client without token is rejected ({detail})")
        ok, detail = asyncio.run(mcp_call("z" * 32))
        check(not ok, f"MCP SDK client with wrong token is rejected ({detail})")
        ok, detail = asyncio.run(mcp_call(token))
        check(ok, f"MCP SDK client with valid token calls hello_mcp ({detail!r})")

        # CORS interaction.
        pre = {
            "Origin": TRUSTED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        r = get(c, "OPTIONS", "/api/invoke", headers=pre)
        allow = r.headers.get("access-control-allow-headers", "").lower()
        check(
            r.status_code == 200
            and "authorization" in allow
            and r.headers.get("access-control-allow-origin") == TRUSTED_ORIGIN,
            f"preflight from trusted origin (no credentials) -> {r.status_code}, allow-headers={allow!r}",
        )
        r = get(c, "OPTIONS", "/api/invoke", headers={**pre, "Origin": OTHER_ORIGIN})
        check(
            r.status_code == 400 and "access-control-allow-origin" not in r.headers,
            f"preflight from untrusted origin -> {r.status_code}, no allow-origin header",
        )
        r = get(c, "GET", "/api/tools", headers={"Origin": TRUSTED_ORIGIN})
        check(
            r.status_code == 401 and r.headers.get("access-control-allow-origin") == TRUSTED_ORIGIN,
            f"401 to trusted origin still carries CORS header -> {r.status_code}",
        )

        dist_index = HERE.parent / "dist" / "index.html"
        if dist_index.exists():
            r = get(c, "GET", "/")
            check(r.status_code == 200, f"GET / (frontend shell) without token -> {r.status_code} (public)")
        else:
            print("[SKIP] GET / (frontend not built: run `npm run build`)")

        check(all(token not in b for b in bodies), "token never appears in any response body")


def scenario_token_unset() -> None:
    section("B. Token not configured (must fail closed)")
    with backends({}), httpx.Client(base_url=BRIDGE, timeout=20.0) as c:
        r = get(c, "GET", "/health")
        check(r.status_code == 200, f"GET /health -> {r.status_code} (liveness stays public)")
        for method, path, kw in [
            ("GET", "/api/status", {}),
            ("GET", "/api/tools", {}),
            ("POST", "/api/invoke", {"json": {"name": "hello_mcp", "arguments": {}}}),
        ]:
            r = get(c, method, path, **kw)
            check(
                r.status_code == 503 and "MCP_CONNECT_API_TOKEN" in r.text,
                f"{method} {path} -> {r.status_code} (auth not configured)",
            )
        r = get(c, "GET", "/api/tools", headers=bearer("any-long-enough-token-value"))
        check(r.status_code == 503, f"/api/tools with an arbitrary token still -> {r.status_code}")
        r = get(httpx.Client(timeout=20.0), "POST", MCP, headers=MCP_HEADERS, json=INIT_BODY)
        check(r.status_code == 503, f"direct POST {MCP} -> {r.status_code}")
        r = get(httpx.Client(timeout=20.0), "POST", MCP, headers={**MCP_HEADERS, **bearer("any-long-enough-token-value")}, json=INIT_BODY)
        check(r.status_code == 503, f"direct POST {MCP} with an arbitrary token still -> {r.status_code}")


def scenario_token_short() -> None:
    section("C. Token too short (must refuse to start)")
    for script in ("run_mcp.py", "app.py"):
        proc = subprocess.run(
            [sys.executable, script],
            cwd=HERE,
            env=_env({"MCP_CONNECT_API_TOKEN": "short"}),
            capture_output=True,
            text=True,
            timeout=30,
        )
        check(
            proc.returncode != 0 and "at least 16 characters" in proc.stderr,
            f"{script} with a 5-character token exits {proc.returncode} with a clear error",
        )


def main() -> int:
    scenario_token_set()
    scenario_token_unset()
    scenario_token_short()
    section("Summary")
    passed = flags.count("PASS")
    print(f"{passed}/{len(flags)} auth checks passed")
    return 0 if passed == len(flags) else 1


if __name__ == "__main__":
    sys.exit(main())
