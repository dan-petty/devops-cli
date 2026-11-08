# Design: Let a Job Call the Tools of the MCP Server

## Decisions
- **pydantic-ai MCP client over streamable HTTP**: Use `pydantic_ai.mcp.MCPToolset`. It integrates with Pydantic AI agents and avoids a custom JSON-RPC implementation.
- **Per-role MCP bearer token from secret resolver**: The stage job uses `mcp.stage_token` and the implement job uses `mcp.implement_token`. The runner pod has no Kubernetes ServiceAccount token, so the secret resolver provides role-scoped credentials.
- **Dedicated start-up error**: When the MCP server is unavailable or connection fails at job start, raise `RoadmapMcpUnavailableError` naming the server URL.
- **Local tool precedence**: Remote tools with names that collide with local tool names are omitted so local tools always win.
- **Remote call timeout**: Bound each remote tool call with `roadmap.mcp.timeout_seconds` (default 30.0s). When a call times out, report a tool error to the model and record the timeout in `RunTrace`.
- **In-process test fake**: Tests use an in-process FastMCP server and ASGI transport with no real sockets or network calls.

## Rejected alternatives
- **ServiceAccount token**: The runner pod has no Kubernetes token.
- **Shared token with role header**: The server cannot trust a client-selected role header.
- **Generic job crash on startup failure**: A generic crash hides the root cause when the MCP server is unreachable.
- **Custom JSON-RPC client**: Reinvents an existing supported library.
