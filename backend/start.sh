#!/usr/bin/env bash
# MCP Connect — backend startup script.
# Starts the MCP server (:8001) and REST bridge (:8000) as detached processes.
# Usage:  bash backend/start.sh
set -euo pipefail

cd "$(dirname "$0")"

# Install deps if missing (idempotent — pip skips already-satisfied packages).
pip install --break-system-packages -q -r requirements.txt 2>/dev/null || true

# Kill any prior instances bound to our ports.
for port in 8000 8001; do
  fuser -k "${port}/tcp" 2>/dev/null || true
done
sleep 1

# Start MCP server (Streamable HTTP on /mcp, port 8001).
nohup python3 run_mcp.py > /tmp/mcp_server.log 2>&1 &
echo "MCP server  -> http://127.0.0.1:8001/mcp  (PID $!)"

# Give the MCP server a moment to bind before the bridge tries to reach it.
sleep 2

# Start REST bridge (serves /health, /api/*, and static frontend, port 8000).
# Binds to 127.0.0.1 by default; it has NO authentication (see README, Security).
nohup python3 app.py > /tmp/rest_bridge.log 2>&1 &
echo "REST bridge -> http://127.0.0.1:8000      (PID $!)"

sleep 2
echo
echo "Verifying..."
python3 verify.py
