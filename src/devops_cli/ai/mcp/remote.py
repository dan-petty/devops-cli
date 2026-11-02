"""The MCP server on the network: one endpoint for each job role, behind one bearer token.

Every role has its own `FastMCP` server that holds only the tools of the role (`roles.py`), and
the HTTP app mounts the servers at `/<role>/mcp`. So the role of a connection is the path that
it called, which the deployment chooses, and nothing the model sends. A tool that a role does not
hold does not exist on its server, so a call by name fails there. The servers share no state:
they have no domain gate and no `hydrate_tool_domain`, so the process-wide `_HYDRATED_DOMAINS` of
the stdio server is never read (#3219).

The server checks the bearer token before any tool runs, with a constant-time comparison, and
refuses to start without one. The `ops` role has no endpoint.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from typing import Any, Final

from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, AuthProvider, TokenVerifier
from fastmcp.server.middleware import Middleware
from fastmcp.utilities.lifespan import combine_lifespans

from devops_cli.ai.mcp.roles import JOB_ROLES, tools_for_role
from devops_cli.ai.mcp.server import ArgumentContractMiddleware, mcp
from devops_cli.exceptions import SecurityError
from devops_cli.lang import ERRORS

logger = logging.getLogger(__name__)

# The path of the MCP endpoint below the path of the role.
_ENDPOINT_PATH: Final = "/mcp"
# A shorter token is easy to guess. `openssl rand -hex 32` gives 64 characters.
_MIN_TOKEN_LENGTH: Final = 32
# The one caller that the bearer token names: the gateway in front of the server.
_CLIENT_ID: Final = "mcp-gateway"


class BearerTokenVerifier(TokenVerifier):
    """Accepts one bearer token, compared in constant time.

    FastMCP's `StaticTokenVerifier` looks the token up in a dict, which compares it with `==`
    and is documented for tests only. This one compares the SHA-256 digests with
    `hmac.compare_digest`, so the time of a refusal tells nothing about the token or its length.
    """

    def __init__(self, token: str) -> None:
        super().__init__()
        check_token(token)
        self._digest = hashlib.sha256(token.encode()).digest()

    async def verify_token(self, token: str) -> AccessToken | None:
        presented = hashlib.sha256(token.encode()).digest()
        if hmac.compare_digest(presented, self._digest):
            return AccessToken(token=token, client_id=_CLIENT_ID, scopes=[])
        return None


class RoleAuditMiddleware(Middleware):
    """Logs each tool call with the role of the server. It logs no argument value, because a
    tool argument can hold a secret (`SECURITY.md`)."""

    def __init__(self, role: str) -> None:
        self._role = role

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        logger.info("MCP tool call: role=%s tool=%s", self._role, context.message.name)
        return await call_next(context)


def check_token(token: str | None) -> str:
    """The token when it can protect a remote server; else `SecurityError`."""
    if not token or not token.strip():
        raise SecurityError(ERRORS.mcp.token_required)
    if len(token) < _MIN_TOKEN_LENGTH:
        raise SecurityError(ERRORS.mcp.token_too_short.format(minimum=_MIN_TOKEN_LENGTH))
    return token


def resolve_token() -> str:
    """The bearer token from the `mcp.token` credential; `SecurityError` when it is missing or
    too short."""
    from devops_cli.config.settings import get_mcp_token, load_settings

    token = get_mcp_token(load_settings())
    return check_token(token.strip() if token else token)


def build_role_server(role: str, *, auth: AuthProvider | None = None) -> FastMCP:
    """A server that holds the tools of `role` and no other tool.

    The tools are the registered objects of the stdio server, so a tool runs the same code on
    either transport. The server has no domain gate and no hydrate tool, and it offers no
    resource or prompt: a resource runs a command with no role check.
    """
    server = FastMCP(
        name=f"devops-cli-{role}",
        instructions=f"DevOps CLI tools for the '{role}' role.",
        auth=auth,
    )
    for tool in tools_for_role(role, asyncio.run(mcp._list_tools())):
        server.add_tool(tool)
    # The audit is the outer layer, so it also logs a call that the argument contract refuses.
    server.add_middleware(RoleAuditMiddleware(role))
    server.add_middleware(ArgumentContractMiddleware(server))
    return server


def build_http_app(token: str) -> FastAPI:
    """The ASGI app that serves `/<role>/mcp` for each job role behind the bearer `token`.

    Each endpoint is stateless and answers in JSON, so no connection keeps state that another
    connection can see. A path that is no role endpoint gives 404, and `ops` has none.
    """
    verifier = BearerTokenVerifier(token)
    role_apps = {
        role: build_role_server(role, auth=verifier).http_app(
            path=_ENDPOINT_PATH,
            transport="streamable-http",
            json_response=True,
            stateless_http=True,
        )
        for role in JOB_ROLES
    }
    app = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=combine_lifespans(*(role_app.lifespan for role_app in role_apps.values())),
    )
    for role, role_app in role_apps.items():
        app.mount(f"/{role}", role_app)
    return app


def serve_streamable_http(host: str, port: int, token: str) -> None:
    """Serve the role endpoints on `host:port` until the process stops."""
    import uvicorn

    # The root logger has no handler in this process, so the audit line would go nowhere.
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    uvicorn.run(build_http_app(token), host=host, port=port, log_level="info")
