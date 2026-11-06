# Tasks

## 1. The tool listing has a snapshot (test-only edits)

- [x] 1.1 Add `tests/ai/mcp/test_mcp_tool_listing.py`, which compares name, description and input schema of every tool with a syrupy JSON snapshot, and write the snapshot with `--snapshot-update`.
  Verification: `uv run pytest tests/ai/mcp/test_mcp_tool_listing.py`

## 2. The MCP tests are named by behavior (test-only edits)

- [x] 2.1 Split `test_fastmcp_contracts.py` and `test_mcp.py` into the files of `proposal.md`, rename `test_fastmcp_in_process.py` to `test_mcp_dispatcher.py`, and move the shared helpers to `tests/support/mcp_client.py` and `tests/ai/mcp/conftest.py`.
  Verification: `uv run pytest tests/ai/mcp tests/commands/test_mcp_serve_stdio_and_sse.py tests/commands/test_mcp_tools_and_schema_export.py`
- [x] 2.2 Check that the old files are gone.
  Verification: `! ls tests/ai/mcp/test_fastmcp_contracts.py tests/ai/mcp/test_mcp.py tests/ai/mcp/test_fastmcp_in_process.py tests/ai/agents/test_pydantic_ai_toolsets.py tests/ai/tools/test_pydantic_ai_tools.py`

## 3. The toolset and tool tests are named by behavior (test-only edits)

- [x] 3.1 Split the toolset tests into `tests/ai/toolsets/` and `tests/ai/agents/test_agent_toolset_registration.py`, and rename the tool tests to `tests/ai/tools/test_tool_definition.py`. The classes become plain functions.
  Verification: `uv run pytest tests/ai/toolsets tests/ai/tools tests/ai/agents/test_agent_toolset_registration.py`
- [x] 3.2 Check that no name in the new files holds `PydanticAI`.
  Verification: `! git grep -n PydanticAIT -- tests/ai/toolsets tests/ai/tools/test_tool_definition.py tests/ai/agents/test_agent_toolset_registration.py`

## 4. No stale name is left (documents)

- [x] 4.1 Fix the old test paths in `docs/TESTING.md`, `tests/invariants/test_hermetic_floor.py` and the plans of the open changes.
  Verification: `! git grep -n -e test_fastmcp_contracts -e test_fastmcp_in_process -e test_pydantic_ai_toolsets -e test_pydantic_ai_tools -e tests/ai/mcp/test_mcp.py -- src tests/invariants docs/TESTING.md README.md ARCHITECTURE.md SECURITY.md CONTRIBUTING.md openspec/changes/3199-post-the-check-results-of-a openspec/changes/3204-scaffold-a-command-and-a-test openspec/changes/3230-decide-the-free-text-mcp-parameters openspec/changes/3236-read-only-tools-take-paths-that openspec/changes/3320-a-plan-that-deletes-a-guard`
- [x] 4.2 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## Workflow follow-up

- The moved bodies still patch `devops_cli` names in a few places (for example `devops_cli.ai.mcp.server.mcp` and `devops_cli.commands.mcp.run_mcp_server`). Issue #1336 bans them.
