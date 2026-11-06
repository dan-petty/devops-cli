# Proposal

## Why

Issue #3762 is Item D of #1330. Outbound MCP means devops-cli as a client of another MCP server. The code for it has no caller. The wrapper class `MCPToolset` in `ai/agents/tools.py` does not connect: its `close` does nothing and its `get_tools` returns the list it was given. The helpers in `ai/mcp/toolset.py` only re-export pydantic-ai. A seam for code with no caller would be zombie code, so the code goes.

## What Changes

- Delete `src/devops_cli/ai/mcp/toolset.py`.
- Delete the class `MCPToolset` from `ai/agents/tools.py`, with its `from_config` and `to_native_toolset`, and the imports that only they used. `AgentSpec` and `AgentTool` stay.
- Delete `PydanticAgent.set_mcp_sampling_model` from `ai/agents/agent.py`.
- Delete `get_devops_mcp_toolset` from `ai/tools/mcp_bridge.py` and from `ai/tools/__init__.py`. `get_mcp_agent_tools` stays: `get_default_tools` calls it.
- Delete `tests/ai/mcp/test_pydantic_ai_mcp.py` and `test_mcp_toolset` in `tests/ai/agents/test_ai_agent_capabilities.py`. The two tests of live code move to `tests/ai/tools/test_default_tools_follow_the_mcp_server.py`, which mirrors `ai/tools/`.
- The knowledge-base examples call pydantic-ai's own `MCPToolset` (`pydantic_ai.mcp`) and not the deleted wrapper. The line that listed outbound MCP servers as a faked edge leaves `docs/TESTING.md`.
- No command, option, setting or message changes. The change has no spec delta, and `skip_specs: true` is set.
- The change fits one pull request.

## Impact

- `src/devops_cli/ai/mcp/`, `ai/agents/` (`tools.py`, `agent.py`), `ai/tools/` (`mcp_bridge.py`, `__init__.py`), two knowledge-base pages and the knowledge-base index.
- `docs/TESTING.md`.
- `tests/ai/mcp/`, `tests/ai/tools/` and `tests/ai/agents/test_ai_agent_capabilities.py`.
- About 155 lines of `toolset.py`, 150 lines of the wrapper class and 300 lines of tests leave the tree.
- Left to other items of #1330: the children A, B, C, E and F.

## Feasibility

Checked on `origin/main` f6286d6b, 2026-11-06. Each claim of the issue was read again in the current tree.

- Callers by name. A `git grep` for `MCPToolset`, `ai.mcp.toolset`, `create_mcp_toolset`, `create_devops_mcp_toolset`, `load_devops_mcp_toolsets`, `get_devops_mcp_toolset` and `set_mcp_sampling_model` (archives excluded) finds only these files: `ai/mcp/toolset.py`, `ai/agents/tools.py`, `ai/agents/agent.py`, `ai/tools/mcp_bridge.py`, `ai/tools/__init__.py`, two knowledge-base pages, `tests/ai/mcp/test_pydantic_ai_mcp.py`, `tests/ai/agents/test_ai_agent_capabilities.py`, and some roadmap-eval fixtures that quote the issue text of #2175.
- Import graph. `ai.mcp.toolset` is imported by `ai/agents/tools.py` (`MCPToolset.to_native_toolset`) and `ai/tools/mcp_bridge.py` (`get_devops_mcp_toolset`) only. Nothing in `src` calls `to_native_toolset`, `from_config` or `get_devops_mcp_toolset`. `ai/agents/agent.py` imports `AbstractToolset`, `AgentSpec`, `AgentTool`, `FunctionToolset`, `Tool`, `ToolCall` and `ToolReturn` from `ai/agents/tools.py`, and no `MCPToolset`.
- No command, setting, tool or entry point reaches an MCP server address or script. `pyproject.toml` has no entry point for the module. A grep for `pydantic_ai.mcp` in `src` finds only `ai/mcp/toolset.py` and one docstring. The roadmap code uses pydantic-ai toolsets and the harness, and none of the deleted names.
- Kept because it has a caller: `get_mcp_agent_tools` (called by `get_default_tools` in `ai/tools/registry.py`), `ai/mcp/remote.py` (the inbound HTTP server, used by `devops mcp serve`), and `generator.py`, `dispatcher.py`, `roles.py`, `argument_contract.py`, `path_confinement.py` and `server.py` of `ai/mcp/`.
- The wrapper does not connect. Read before the change, `close` is `pass` and `get_tools` returns `self.tools`.
- The knowledge-base examples were checked against the installed package (`pydantic-ai-slim` 2.59.0). `inspect.signature(pydantic_ai.mcp.MCPToolset.__init__)` shows `client` as the first argument and the keywords `http_client` and `sampling_model` (a `Model`). The old example passed a model name and a dict for `client_info`, which do not match.
- Related items: #3221 plans a job-side MCP client with pydantic-ai's own class, so the deletion does not block it. #2489 deletes `PydanticAgent`. Whichever item lands first removes `set_mcp_sampling_model`.

## Existing Tool Considered

The open, maintained tool for an outbound MCP client is pydantic-ai's own `MCPToolset` (`pydantic_ai.mcp`) over FastMCP's client. The deleted wrapper only re-exported or imitated it. Nothing needs a wrapper today, so the change adds no tool and no seam. The cost of a seam for code with no caller is about 60,000 tokens to build and 20,000 tokens a year to keep, with one day of elapsed time. The cost of this deletion is no new code. The internal code that leaves the tree is listed in What Changes.
