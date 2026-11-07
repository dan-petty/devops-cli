# Proposal

## Why

Issue #3765 is child F of #1330. Five test files of the MCP server, the toolsets and the tools carry the name of a library or hold many behaviors. A failing file does not say which behavior broke. The tool listing that clients receive has no snapshot, so a change to a tool name, description or input schema passes unseen.

| File at origin/main a0f95577 | Lines | Tests | Problem |
| :--- | :--- | :--- | :--- |
| `tests/ai/mcp/test_fastmcp_contracts.py` | 1,644 | 75 | Registry, prompts, argv of tools, dispatch logging, domain hydration, argument refusal and schemas in one file |
| `tests/ai/mcp/test_mcp.py` | 858 | 175 | Exposure table, scan tools, server start, run-command results, and the `devops mcp` command in one file |
| `tests/ai/mcp/test_fastmcp_in_process.py` | 237 | 11 | Named after the library, tests the dispatcher |
| `tests/ai/agents/test_pydantic_ai_toolsets.py` | 342 | 13 | Named after the library, one class `TestPydanticAIToolsetsSubsystem`, tests `ai/toolsets` |
| `tests/ai/tools/test_pydantic_ai_tools.py` | 134 | 5 | Named after the library, one class `TestPydanticAIToolsSubsystem` |

Counts are test ids from `pytest --collect-only`, so a parametrized test counts once for each case.

## What Changes

- The five files are gone. Their 279 tests move, with the same names and the same bodies, into 22 files. Each file holds one behavior and is named by it. No new file is longer than 600 lines. The longest one has 461.
  - `tests/ai/mcp/`: `test_mcp_tool_registry.py`, `test_mcp_prompts_and_resources.py`, `test_mcp_messages.py`, `test_mcp_dispatch_logging.py`, `test_mcp_domain_hydration.py`, `test_mcp_argument_refusal.py`, `test_mcp_tool_schemas.py`, `test_mcp_telemetry_profile.py`, `test_mcp_roadmap_tools.py`, `test_mcp_tool_argv.py`, `test_mcp_exposure_table.py`, `test_mcp_run_command.py`, `test_mcp_scan_tools.py`, `test_mcp_server_start.py`, and `test_mcp_dispatcher.py` (the rename of `test_fastmcp_in_process.py`).
  - `tests/commands/`: `test_mcp_serve_stdio_and_sse.py` and `test_mcp_tools_and_schema_export.py` take the cases of `devops mcp serve`, `devops mcp tools` and `devops mcp export-schemas`, which test `commands/mcp.py`. The text of #3765 says child B moved them already. It did not (see Feasibility).
  - `tests/ai/toolsets/` (new, mirrors `src/devops_cli/ai/toolsets/`): `test_function_toolset.py`, `test_toolset_combinators.py`, `test_toolset_authoring.py`.
  - `tests/ai/agents/test_agent_toolset_registration.py` holds the one test that builds a `PydanticAgent` from a toolset. It stays with the agent tests that #2489 rewrites.
  - `tests/ai/tools/test_tool_definition.py`.
- Test classes become plain test functions. No test, class or function name holds `PydanticAI` or `pydantic_ai`.
- Two helpers that several new files share leave the old file. `call_tool` and `published_schemas` (the former `_call` and `_published_schemas`) move to `tests/support/mcp_client.py`. The fixtures `handler_runner` and `fastmcp_log` move to `tests/ai/mcp/conftest.py`.
- A new test, `tests/ai/mcp/test_mcp_tool_listing.py`, compares the name, description and input schema of each tool, from `mcp.list_tools(run_middleware=False)`, with one syrupy `JSONSnapshotExtension` snapshot. The snapshot is `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json` (145 tools, 180 KB). The JSON keys are sorted, so the order of the tools is by name.
- Stale names are fixed in `docs/TESTING.md`, in the invariant `tests/invariants/test_hermetic_floor.py` and in the plans of the open changes 3199, 3204, 3230, 3236 and 3320.
- No product code changes. The change has no spec delta, so `skip_specs: true` is set.
- The change fits one pull request.

Test counts: 279 before, 279 after, plus 1 new (the snapshot test). No test is merged or deleted. A script compared the multiset of test names of the five old files with the multiset of the 22 new files: both are equal.

## Impact

- `tests/ai/mcp/`, `tests/ai/toolsets/`, `tests/ai/tools/`, `tests/ai/agents/`, `tests/commands/`, `tests/support/mcp_client.py`, `tests/invariants/test_hermetic_floor.py`, `docs/TESTING.md`.
- `openspec/changes/3199-*`, `3204-*`, `3230-*`, `3236-*`, `3320-*`: only the paths of test files.
- Out of scope: the `devops_cli` patches and private imports that the moved bodies still hold. Child B (#3760) left them with the items that own them, and #1336 bans them. This change keeps each body unchanged, so a reviewer sees pure moves.

## Feasibility

Checked on `origin/main` a0f95577, 2026-11-06. The text of #3765 was written at 29309f04, so each claim was read again.

- The five files exist. Child B (#3760) is closed and merged, so the dependency holds. `ls tests/ai/mcp` shows `test_dispatcher_contract.py`, the file of child B.
- The claim "Child B already moved the CLI cases to `tests/commands/test_mcp_serve.py`" is false. `tests/commands/test_mcp_serve.py` holds only the cases of the `streamable-http` transport (#3219). `TestMcpCli` and the dry-run cases of `devops mcp` were still in `test_mcp.py`. They test `commands/mcp.py`, so they go to `tests/commands/`.
- Count of the listing: `await mcp.list_tools(run_middleware=False)` returns 145 tools. The JSON with two-space indent has 181,909 characters. The snapshot file has 180,315 bytes. A second run of the snapshot test, in another process, left the file unchanged. The file holds no absolute path (a search for `/workspaces` and `/home/` finds none).
- syrupy 6.1.1 is pinned in `pyproject.toml`. I read `JSONSnapshotExtension` in the installed package: it sorts the keys of each dict and writes one file for each test, under `__snapshots__/<module>/`.
- The moved tests still catch faults. I changed `src/devops_cli/ai/mcp/server.py` in the work tree, ran the new files, and restored the file. Three edits: the text "Command exited with status" of the tool error, `_is_advertised` returning true for every tool, and `show_banner=False` of the stdio start. Six tests failed in `test_mcp_run_command.py`, `test_mcp_domain_hydration.py` and `test_mcp_server_start.py`. Adding the parameter `extra` to `security_intel_network` made the snapshot test fail.

## Existing Tool Considered

syrupy (pinned `6.1.1`, already used for `tests/ci/__snapshots__/test_fail_to_pass.ambr`) with its `JSONSnapshotExtension` makes the snapshot. FastMCP's own `list_tools` supplies the listing. pytest, `git mv` and `ruff` do the moves and the import clean-up. Nothing is built. The change deletes no source code. It deletes the five old test files and the two private helpers `_call` and `_published_schemas`, which become public helpers in `tests/support/mcp_client.py`.
