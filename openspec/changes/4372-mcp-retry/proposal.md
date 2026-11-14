# Proposal

## Why

A new roadmap Job pod can fail its first MCP connection until kube-router programs the network policy of the pod. The MCP client raises `RoadmapMcpUnavailableError` on that first refusal and the job stops (#4372).

## What Changes

- `RoadmapMcpToolset.__aenter__` retries a refused connection with tenacity for `ROADMAP_MCP_CONNECT_RETRY_SECONDS`, with exponential delays from `ROADMAP_MCP_CONNECT_RETRY_INITIAL_SECONDS` capped at `ROADMAP_MCP_CONNECT_RETRY_MAX_SECONDS`.
- An exhausted budget raises `RoadmapMcpUnavailableError` with the target URL and the last connection error as its cause.
- An authentication failure is not retried.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-mcp-client`: The client retries a first connection that the policy start delay refuses.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/mcp.py`
- Tests: `tests/roadmap/test_roadmap_mcp_connect_retry.py`

## Feasibility

- `route_with_jev` is unrelated; tenacity is already a dependency and the repository uses it.
- The MCP client is one `__aenter__`.
- Verification commands: `uv run devops ci test tests/roadmap/test_roadmap_mcp_connect_retry.py tests/roadmap/test_roadmap_mcp.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

tenacity 9.1.4 is already a dependency and covers a bounded async retry with exponential backoff and a predicate. No new library.
