"""MCP Connect — shared bearer-token authentication.

A small, dependency-free ASGI middleware used by BOTH processes (the REST
bridge and the MCP server), so neither relies on the other for protection.

Configuration:
  MCP_CONNECT_API_TOKEN  shared secret; clients send "Authorization: Bearer <token>".

Behaviour (fails closed):
  - token not set       -> protected paths answer 503 (auth not configured)
  - token too short     -> process refuses to start (RuntimeError)
  - missing/invalid     -> 401 with "WWW-Authenticate: Bearer"
  - valid               -> request passes through
The token is compared in constant time and is never logged or echoed.
"""
from __future__ import annotations

import hmac
import json
import os
from typing import Any, Callable

TOKEN_ENV = "MCP_CONNECT_API_TOKEN"
MIN_TOKEN_LENGTH = 16


def load_token() -> str | None:
    """Read the shared token from the environment.

    Returns None when unset (protected paths will answer 503). Raises when the
    token is set but too short to be a credible secret.
    """
    raw = os.environ.get(TOKEN_ENV, "").strip()
    if not raw:
        return None
    if len(raw) < MIN_TOKEN_LENGTH:
        raise RuntimeError(
            f"{TOKEN_ENV} must be at least {MIN_TOKEN_LENGTH} characters long."
        )
    return raw


class BearerAuthMiddleware:
    """Pure-ASGI bearer-token check (safe for streaming/SSE responses)."""

    def __init__(
        self,
        app: Any,
        token: str | None,
        protect: Callable[[str], bool],
    ) -> None:
        self.app = app
        self._token = token.encode("utf-8") if token else None
        self._protect = protect

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        scope_type = scope["type"]
        if scope_type not in ("http", "websocket") or not self._protect(scope["path"]):
            await self.app(scope, receive, send)
            return

        if scope_type == "websocket":
            # No websocket endpoints exist; refuse rather than pass through.
            await send({"type": "websocket.close", "code": 1008})
            return

        if self._token is None:
            await self._respond(
                send,
                503,
                f"Authentication is not configured on the server. Set {TOKEN_ENV}.",
            )
            return

        if not self._authorized(scope):
            await self._respond(
                send, 401, "Unauthorized", {b"www-authenticate": b"Bearer"}
            )
            return

        await self.app(scope, receive, send)

    def _authorized(self, scope: dict) -> bool:
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                scheme, _, credential = value.partition(b" ")
                if scheme.lower() != b"bearer":
                    return False
                assert self._token is not None
                return hmac.compare_digest(credential.strip(), self._token)
        return False

    @staticmethod
    async def _respond(
        send: Any,
        status: int,
        message: str,
        extra_headers: dict[bytes, bytes] | None = None,
    ) -> None:
        body = json.dumps({"ok": False, "error": message}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store"),
        ]
        headers.extend((extra_headers or {}).items())
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
