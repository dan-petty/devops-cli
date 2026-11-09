# Proposal: #4255

## Why

The citation gate of the stage job read any quoted string tuple in a plan as a key of `CONST_MCP_EXPOSURE_TABLE`. The live run on item #4062 cited `("reset_logfire_bridge",)`, an entry of another table in `tests/conftest.py`, and the gate refused the plan. The plan did not talk about the MCP exposure table (#4255).

## What Changes

- `_mcp_exposure_problems` checks a quoted tuple only when its sentence names `CONST_MCP_EXPOSURE_TABLE` or the words "exposure table". A tuple in any other sentence is not checked.
- The tests that cited a bare key now cite it in a sentence that names the exposure table.
- The requirement "Resolve cited MCP exposure keys" says where the gate reads a quoted tuple. The change alters what the stage job accepts, so it carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: a cited MCP exposure key is read only in a sentence that names the exposure table.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_commands.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_command_citations.py`
- The change fits one pull request.

## Feasibility

- The live run of 2026-11-09 on item #4062 refused a plan with "The plan cites the MCP exposure table key (\"reset_logfire_bridge\",), but CONST_MCP_EXPOSURE_TABLE does not have it."
- `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py` holds 143 rows. Each key is a command path of two or more lowercase words, for example `("ai", "ast", "graph")`. A one-word tuple with an underscore can never be a key, and a plain key shape check would not tell a two-word tuple of another table from a key.
- The new test `test_a_quoted_tuple_of_another_table_is_no_mcp_key` and `test_the_sentence_of_the_tuple_decides_the_context` fail on origin/main and pass with the change.
- The golden set of the stage eval replays through the gates: `uv run devops roadmap eval stage --replay` accepts 5 of 5 good plans.

## Existing Tool Considered

The standard library `re` and `ast`, which the gate uses now. No parser for Markdown prose covers a sentence rule this small. The change adds two compiled patterns and one helper of 8 lines, and deletes no code. The cost to build is low: about 2 hours of tokens and time to keep it in step with the sentence form of plans.
