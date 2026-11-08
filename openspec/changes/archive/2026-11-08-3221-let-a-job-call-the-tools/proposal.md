# Change: Let a Roadmap Job Call the Tools of the MCP Server (#3221)

## Why
The planner, the refine investigation, the alternatives check and the implement step use tool classes that run in the job. Nothing in `src/` uses a Model Context Protocol (MCP) client. A job cannot use a tool that its image lacks. This change lets the stage and implement jobs add the read-only tools of their role from the MCP server without a new image.

Closes #3221.

## What Changes
- Add `roadmap.mcp.url` and `roadmap.mcp.timeout_seconds` configuration settings.
- Add `roadmap.stage.mcp` and `roadmap.implement.mcp` job configuration switches.
- Add `mcp.stage_token` and `mcp.implement_token` credentials to the secret registry.
- Add `RoadmapMcpUnavailableError` to `src/devops_cli/exceptions/roadmap.py`.
- Add `RoadmapMcpToolset` in `src/devops_cli/roadmap/mcp.py` to connect to the role endpoint with the per-role bearer token.
- Connect to `/planning/mcp` in stage job and `/implementation/mcp` in implement step when the MCP switch is active.
- Enforce local-tool precedence so a local tool always wins on a name clash.
- Bound each remote call by `roadmap.mcp.timeout_seconds` and record call outcome and timeout in `RunTrace`.
- Ensure remote call failures reach the model as tool errors and do not abort the job.
- Stop the job with `RoadmapMcpUnavailableError` when the MCP server is down at start.

## Capabilities

### New Capabilities
- `roadmap-mcp-client`: Client integration connecting roadmap jobs to role-scoped remote MCP tools over streamable HTTP.

## Feasibility
Confirmed against upstream documents, code and command output:
- `pydantic-ai` version 2.59.0 provides `MCPToolset` over streamable HTTP.
- FastMCP streamable HTTP endpoints exist for roles `planning`, `implementation` and `review`.
- In-process ASGI transport tests connect to role endpoints without network.

## Existing Tool Considered
`pydantic-ai` MCP client (`pydantic_ai.mcp.MCPToolset`) is the maintained open library that covers MCP connections. Building a custom client would cost approximately 120k tokens and 6 hours. This change integrates `pydantic-ai` with configuration settings, local tool precedence, startup health checks and trace tracking.
