# MCP Connect — Prototype

A connectivity and controlled execution layer that enables AI agents to
interact with external tools through the **Model Context Protocol (MCP)**.

This is a small, functional prototype that demonstrates a **genuine** MCP
connection: a real MCP server (official Python MCP SDK, Streamable HTTP
transport) and a real MCP client that connects to it, discovers tools, and
invokes them. Nothing is mocked.

## Architecture

Two separate processes form the backend, plus a React frontend:

```
┌────────────────┐     HTTP (REST)      ┌──────────────────┐     MCP (Streamable HTTP)     ┌─────────────────┐
│  React frontend │ ───────────────────▶ │  REST bridge     │ ───────────────────────────▶ │  MCP server      │
│  (Vite, :5173)  │  /api/*  /health     │  (Starlette:8000)│   client → /mcp on :8001      │  (Starlette:8001)│
└────────────────┘                      └──────────────────┘                                └─────────────────┘
```

- **MCP server** (`backend/run_mcp.py`): serves the `/mcp` Streamable HTTP
  endpoint using the official MCP SDK's `MCPServer.streamable_http_app()`.
  Defines the `hello_mcp` tool.
- **REST bridge** (`backend/app.py`): a thin Starlette app the frontend talks
  to. Every `/api/*` request opens a **real MCP client session** (official SDK,
  `streamable_http_client`) against the MCP server. Tool discovery and
  invocation go through the actual MCP protocol — they are not simulated.
- **Frontend** (`src/`): a React + TypeScript dashboard showing connection
  status, server info, discovered tools, and a panel to invoke `hello_mcp`.

### Why a REST bridge?

MCP clients run server-side (Python), not in the browser. The bridge exposes
the genuine MCP client/server interaction to the UI over plain HTTP, keeping
all MCP logic and credentials off the frontend.

### Why two processes?

The REST bridge uses an MCP client that connects over HTTP to the MCP server.
Running both in one process causes an event-loop loopback deadlock (the client
blocks on a response the server can't send until the client yields). Splitting
them onto separate ports (8001 / 8000) is the clean, correct architecture.

## Project structure

```
backend/
  mcp_server.py      MCP server + hello_mcp tool definition (official MCP SDK)
  run_mcp.py         Entrypoint: serves the MCP /mcp endpoint on :8001
  app.py             REST bridge: /health, /api/status, /api/tools, /api/invoke on :8000
  auth.py            Shared bearer-token middleware used by both processes
  verify.py          Independent verification script (5 checks; needs the token)
  test_auth.py       Authentication tests (starts its own throwaway backends)
  requirements.txt   Python dependencies
src/
  App.tsx            Dashboard: status, server info, tools, execution, response
  lib/api.ts         Frontend API client (calls the REST bridge)
  lib/types.ts       Shared TypeScript types
```

## Security — read before deploying

**Authentication is a first step, not production-ready.** The REST bridge
(`/api/*`) and the MCP server (`/mcp`) each require a shared bearer token:
`Authorization: Bearer <token>`, taken from `MCP_CONNECT_API_TOKEN`.

- It fails closed. With no token configured, protected paths answer **503**; a
  token shorter than 16 characters stops the process from starting; a missing
  or wrong token gets **401**. Tokens are compared in constant time and never
  logged or echoed.
- Public by design: `/health` and the static frontend (so the page can load and
  ask for the token). Everything under `/api/` and all of `/mcp` is protected.
- This is one shared secret with no users, roles, expiry or rotation, and no
  TLS. **Per-user authentication/authorization, TLS and rate limiting are still
  required before any production or public deployment.** Do not expose either
  port to the internet or an untrusted network until then.
- Both processes bind to `127.0.0.1` by default. Keep it that way for local
  development. Changing `MCP_CONNECT_HOST` / `MCP_SERVER_HOST` to a public
  interface is unsafe without TLS and stronger authentication in front.
- The frontend asks for the token when the backend answers 401 and keeps it for
  that browser tab only (`sessionStorage`).
- **CORS is deny-by-default.** No cross-origin access is granted unless you list
  trusted origins explicitly. A wildcard `*` is rejected at startup.

### Configuration

| Variable                    | Used by            | Default                      | Purpose |
|-----------------------------|--------------------|------------------------------|---------|
| `MCP_CONNECT_API_TOKEN`     | bridge, MCP server, verify.py | *(unset — protected paths return 503)* | Shared bearer token, at least 16 characters. Use the same value for both processes. Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `MCP_CONNECT_CORS_ORIGINS`  | bridge             | *(empty — no CORS)*          | Comma-separated trusted origins, e.g. `http://localhost:5173` |
| `MCP_CONNECT_HOST` / `MCP_CONNECT_PORT` | bridge | `127.0.0.1` / `8000`         | Bridge bind address |
| `MCP_SERVER_HOST` / `MCP_SERVER_PORT`   | MCP server | `127.0.0.1` / `8001`     | MCP server bind address |
| `MCP_CONNECT_MCP_URL`       | bridge, verify.py  | `http://127.0.0.1:8001/mcp`  | Where the bridge/verifier reach the MCP server |
| `MCP_CONNECT_BASE_URL`      | verify.py          | `http://127.0.0.1:8000`      | Bridge URL to verify (or pass as argv[1]) |

## Technology and dependencies

| Layer    | Stack                                      |
|----------|--------------------------------------------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, lucide-react |
| Backend  | Python 3.13, official MCP SDK (`mcp` 2.3.0), Starlette, Uvicorn, httpx |
| Transport| MCP Streamable HTTP                        |

No paid services. No database required for this prototype.

## Features implemented

1. Clean, responsive dashboard displaying MCP Connect.
2. MCP server connection status (live probe via real MCP client).
3. Tool discovery section (`tools/list` over MCP).
4. Test interface to invoke the `hello_mcp` tool.
5. Response panel showing the actual tool result / errors.
6. `/health` endpoint returning HTTP 200.

## Running locally

### Prerequisites

- Python 3.12+ with `pip`
- Node.js 18+ with `npm`

### 1. Backend

```bash
cd backend
pip install -r requirements.txt   # or: pip install "mcp[cli]" uvicorn starlette httpx

# Both processes (and verify.py) need the same token. Do not commit it.
export MCP_CONNECT_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Terminal 1 — start the MCP server
python3 run_mcp.py                 # serves /mcp on http://127.0.0.1:8001

# Terminal 2 — start the REST bridge
python3 app.py                     # serves /health + /api/* on http://127.0.0.1:8000
```

### 2. Verify (independent)

```bash
cd backend
python3 verify.py                  # runs 5 checks, expects 5/5 PASS (needs MCP_CONNECT_API_TOKEN)
python3 test_auth.py               # authentication tests (own throwaway backends; token not needed)

# Non-default ports / hosts:
MCP_CONNECT_MCP_URL=http://127.0.0.1:9001/mcp python3 verify.py http://127.0.0.1:9000
```

### 3. Frontend

```bash
npm install
npm run dev                        # Vite dev server on http://127.0.0.1:5173
```

Open http://127.0.0.1:5173 — the dashboard talks to the REST bridge via a
Vite proxy (see `vite.config.ts`).

## Tests performed and results

Run `python3 backend/verify.py`:

| #  | Check                                          | Result |
|----|------------------------------------------------|--------|
| 1  | `/health` returns HTTP 200                     | PASS   |
| 2  | `/api/status` reports connected MCP session     | PASS   |
| 3  | `/api/tools` discovers `hello_mcp`              | PASS   |
| 4  | `/api/invoke` calls `hello_mcp`, returns greeting| PASS   |
| 5  | Direct MCP client (bypassing bridge) connects   | PASS   |

Frontend: `npm run build` and `npm run typecheck` both pass.

## Evidence of genuine MCP connectivity

- The MCP server is created with the official `mcp.server.mcpserver.MCPServer`
  and served via `streamable_http_app()` — the SDK's Streamable HTTP transport.
- The REST bridge and the verify script both use
  `mcp.client.streamable_http.streamable_http_client` +
  `mcp.client.session.ClientSession` — the official MCP client — to perform
  `initialize`, `tools/list`, and `tools/call`.
- Verified protocol version negotiated: `2025-11-25`.
- Verified server info returned over MCP: `mcp-connect v0.1.0`.
- The `hello_mcp` tool returns `Hello, <name>! MCP Connect is online.` from the
  real tool implementation — not a hardcoded response.
- Check 5 in `verify.py` bypasses the REST bridge entirely and connects a
  standalone MCP client directly to `/mcp`, proving the bridge is not a
  shortcut around the protocol.

## Known issues

- The Python venv module (`python3-venv`) is not installable in this sandbox
  without root, so `mcp` was installed with `pip --break-system-packages`.
  In a normal environment, use a virtualenv: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- The frontend dev server and backend run on different ports; local dev uses the
  Vite proxy (`vite.config.ts`), so no CORS is needed. CORS is deny-by-default
  (see Security).

## Outstanding work

- Add more MCP tools beyond `hello_mcp` (the architecture supports them).
- **Replace the shared bearer token with per-user authentication/authorization, add TLS and rate limiting (required before production).**
- Add automated frontend tests.
- Containerize the backend for reproducible deployment.
