# Proposal: #6461

## Why

#6461: #2176 merged on 2026-11-19 (PR #6436) while its mutation campaign still ran. The mutation record of PR #6436 (comment 7017160746) left 13 rows with the decision `pending`. Each of these test files can kill mutants that no other file kills, or it can be a copy of checks that other files hold. Until a row has a decision, the suite keeps tests that add no check, or a later wave can delete a file that holds the only check of a line.

## What Changes

- Each of the 13 pending rows gets a decision by the method of the record of #2176: run 1 selects the file alone, run 2 runs each mutant that run 1 killed against the other files that run its statement, and run 3 runs each survivor of a sampled mutant against all of those files. A mutant whose statement no other file runs is own with no run 2.
- A row with an own mutant keeps its file whole (`kept`), and the record names its own mutants and the test that kills them. A row with no own mutant loses the tests that `## Weakened checks` of the #2176 proposal names: the file goes (`deleted`) or keeps only its unjudged cases (`trimmed`).
- A new record comment on the pull request of this item lists each decision, the run counts and the own mutants. No committed file holds the record.
- The change alters no behavior that a consumer observes. It removes or keeps tests only, so it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: the 13 test files of the pending rows (`tests/commands/test_config.py`, `tests/ai/client/test_ai_client_credentials.py`, `tests/ai/test_ai_client_style_request.py`, `tests/ai/client/test_ai_gateway_base_url.py`, `tests/ai/spend/test_ai_spend_dispatch.py`, `tests/config/test_settings_cache.py`, `tests/ai/benchmark/test_data_dir_configuration.py`, `tests/docs/test_exceptions.py`, `tests/config/test_headless_auth.py`, `tests/http/test_http_async_client.py`, `tests/ai/retries/test_pydantic_ai_retries.py`, `tests/valkey/test_valkey_cache_tier.py`, `tests/commands/test_dependency_audit.py`) and `tests/module_durations.json` when a file goes.
- No source file changes. Line and branch coverage and `fail_under` stay the same or rise.

## Feasibility

Checked on 2026-11-19 at `origin/main` (7dd00afe7).

- Each of the 13 files exists on `origin/main`: `git show origin/main:<path> | wc -l` gives a line count for each.
- The record comment 7017160746 gives the method and the state of each row. Run 1 ended for 8 rows (credentials, settings cache, data dir, exceptions, headless auth, HTTP async, dependency audit, style request). Five rows (config, gateway base URL, spend dispatch, retries, Valkey tier) had no run 1.
- The per-test coverage data of commit 633021ead names, for each mutant that run 1 killed, the test files that run its statement. For credentials, headless auth, exceptions and dependency audit, some of these mutants have no other file, so the rows have own mutants.
- Runs inside a git checkout stop at the host path guard (#6448). The run folders are outside every checkout, with `git init -q` in the mutants tree, and that form works today.

## Existing Tool Considered

mutmut 3.8.1, the mutation tool of the project, runs every campaign. The selection per row uses `pytest_add_cli_args_test_selection` of `[tool.mutmut]` in `pyproject.toml`, and coverage.py with `--cov-context=test` gives the files that run each statement. The change adds no code to the repository. The scripts that make the run folders stay outside git.
