# Tasks

## 1. Delete the outbound MCP code and its tests (deletion)

- [x] 1.1 Delete `ai/mcp/toolset.py`, the class `MCPToolset` of `ai/agents/tools.py`, `PydanticAgent.set_mcp_sampling_model` and `get_devops_mcp_toolset`, with the imports and exports that only they used.
  Verification: `! git grep -nE 'devops_cli\.ai\.agents\.tools import .*MCPToolset|ai\.mcp\.toolset|create_mcp_toolset|create_devops_mcp_toolset|load_devops_mcp_toolsets|get_devops_mcp_toolset|set_mcp_sampling_model' -- src docs tests ':!docs/agent/archive' ':!tests/fixtures'`
- [x] 1.2 Delete `tests/ai/mcp/test_pydantic_ai_mcp.py` and `test_mcp_toolset`. Move the two tests of live code to `tests/ai/tools/test_default_tools_follow_the_mcp_server.py`.
  Verification: `uv run pytest tests/ai/tools tests/ai/agents/test_ai_agent_capabilities.py tests/ai/mcp`
- [x] 1.3 Check the style rules for the changed code.
  Verification: `uv run ruff check src tests`

## 2. Documents (documents)

- [x] 2.1 Make the knowledge-base examples call pydantic-ai's own `MCPToolset`, and drop the outbound MCP edge from `docs/TESTING.md`.
  Verification: `uv run devops ci --check --only docs`
- [x] 2.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`
