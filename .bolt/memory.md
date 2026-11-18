# Project memory

## Product intent & audience

- Prototype demonstrating real Model Context Protocol (MCP) connectivity, tool discovery, and tool execution.
- Dashboard UI showing live connection status, discovered tools, and tool execution results.
- Audience: developers/evaluators verifying genuine MCP protocol behavior (not mocked).

## Brand personality & voice

- Verification-first: user expects actual terminal execution and test results, not descriptions of what should be done.
- Concise status reporting with pass/fail checklists.
- No mock data, no scope expansion — real data only.

## Visual design & UX direction

- Dashboard with connection status indicator ("Connected" / "Disconnected").
- Displays discovered tools list and tool invocation results.
- Vite + React + TypeScript frontend; Tailwind CSS for styling; Lucide React for icons; `@/` path alias to `src/`.
- Frontend proxies `/api` and `/health` to `127.0.0.1:8000` (REST bridge).

## Decisions, constraints & rationale

- **Backend architecture:** Two long-running Python processes:
  - MCP server: `run_mcp.py` on port **8001**.
  - REST bridge: `app.py` on port **8000** — exposes `/health`, `/api/status`, `/api/tools`, `/api/invoke` and translates HTTP to MCP protocol.
- **Startup script:** `backend/start.sh` — installs deps, kills stale processes on 8000/8001, starts both servers, runs verification. Use after any environment reset.
- **Dependency install:** `pip install --break-system-packages -r backend/requirements.txt` required in this environment.
- **MCP protocol version:** `2025-11-25`; server identifies as `mcp-connect v0.1.0`.
- **Sample tool:** `hello_mcp` — accepts a `name` parameter, returns `"Hello, {name}! MCP Connect is online."`
- **Environment constraint:** Sandbox resets kill both backend processes and wipe installed packages; they do not auto-restart. Manual restart via `backend/start.sh` is the recovery path.
- **Do not** rebuild the app, introduce mock data, or expand scope.

## Open questions & assumptions

- Whether the environment will persist long-running processes across turns remains unreliable; assume a reset may occur at any time.
- No auto-restart/watchdog mechanism exists yet; unclear if one should be added or if manual `start.sh` is sufficient for a prototype.
- Frontend proxy configuration assumed to be in Vite config; not yet inspected in detail.