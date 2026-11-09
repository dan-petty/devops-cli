# Proposal: #3769

## Why

Command tests must double external edges and not internal names of `devops_cli`.
The tests in `tests/commands` previously patched internal symbols with `patch` and `monkeypatch.setattr`.
This pull request converts the final set of command tests to use hermetic edge doubles and removes all remaining internal string patches.
It also updates the invariant check so `tests/commands` is verified as patch-free.
Closes #3769.

## What Changes

- Remove all internal string patches of `devops_cli` names across `tests/commands/test_argo_dry_run.py`, `tests/commands/test_mcp_serve_stdio_and_sse.py`, `tests/commands/test_memory_profiler.py`, `tests/commands/test_scan.py`, `tests/commands/test_ai_cmd.py`, `tests/commands/test_telemetry_profile.py`, and `tests/commands/test_analyze.py`.
- Use edge doubles (`ProcessFake`, `GitHubApiFake`, `ModelFake`, `ScannerFake`, `WebFake`, `config`, and `clock`) instead of internal mocks.
- Fix `ModelFake._materialize_answer` to raise `BaseException` candidates (such as `KeyboardInterrupt`).
- Update `devops_cli.commands.analyze.analyze_path` to resolve repository root via `find_repo_root()`.
- Add `"tests/commands"` to `_PATCH_FREE_COMMAND_TEST_DIRECTORIES` in `tests/invariants/test_source_tree.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/analyze.py`.
- Tests: `tests/commands/`, `tests/support/fakes/model.py`, `tests/support/fakes/process.py`, `tests/invariants/test_source_tree.py`.
- Resolves issue #3769 and unblocks issue #1336.

## Feasibility

- Scanned `tests/commands/` using `_string_patches_of_devops_cli`. 0 string patches of `devops_cli` remain.
- All 3,515 tests in `tests/commands/` pass.
- All 19 tests in `tests/invariants/test_source_tree.py` pass.

## Existing Tool Considered

No new tool needed. The test framework fakes (`ProcessFake`, `GitHubApiFake`, `ModelFake`, `ScannerFake`, `WebFake`, `config`) already exist.
