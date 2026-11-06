# Design

## Context

See proposal.md for the scope (#3762, Item D of #1330). The change deletes code and adds no behavior.

## Decisions

### 1. Delete the outbound MCP code, build no seam
- **Decision**: Remove the wrapper, the helper module and their tests. Add no Protocol, no fake and no hook.
- **Why**: A seam needs a caller. The import graph in proposal.md shows none. If a caller appears, that item uses pydantic-ai's `MCPToolset` and tests it with FastMCP's in-memory transport.
- **Rejected**: A fake and a contract suite for outbound MCP. They would double an edge that no code in `src` reaches, so the contract suite would hold the fake to nothing.

### 2. Keep `get_mcp_agent_tools`
- **Decision**: `ai/tools/mcp_bridge.py` stays with `get_mcp_agent_tools` only.
- **Why**: `get_default_tools` calls it, and it gives the agents the tools of the devops-cli server. Its test and the schema-match test move to `tests/ai/tools/`, the mirror of `ai/tools/`.

### 3. The knowledge-base pages keep the pattern for pydantic-ai's client
- **Decision**: The pages keep one example each of `pydantic_ai.mcp.MCPToolset`, marked as not wired in devops-cli.
- **Why**: #3221 cites the page as the pattern. The examples now match the installed signature.
