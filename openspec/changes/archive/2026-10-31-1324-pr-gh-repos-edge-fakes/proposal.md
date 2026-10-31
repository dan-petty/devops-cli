# Proposal

## Why

Issue #1324: GitHub-facing commands (`devops pr`, `devops gh`, and `devops repos`) hold domain logic and patch devops-cli internals in their tests.

- The commands hold domain logic: `commands/gh.py` reads and formats rate limits, `commands/pr.py` plans branch updates, and `commands/repos.py` parses clone URLs.
- The tests for these commands patch internal modules, import private names, and build ad-hoc mock objects.
- `tests/test_pr_cmd.py` holds committed repository file tests for `.github/pull_request_template.md` rather than testing CLI behaviour.

## What Changes

- Move rate-limit reading, payload parsing, and table row formatting from `commands/gh.py` to `devops_cli.github.rate_limit_view`.
- Move branch-update planning functions from `commands/pr.py` to `devops_cli.github.branch_update`.
- Move clone destination parsing from `commands/repos.py` to `devops_cli.git.operations`.
- Move pull request template invariant tests from `tests/test_pr_cmd.py` to `tests/invariants/test_pull_request_template.py`.
- Add `test_pull_request_template.py` to the invariant test files list in `docs/TESTING.md`.
- Route GitHub and process calls in the command tests through shared fakes (`ProcessFake`, `GitHubApiFake`).

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- None.

## Impact

- Source files: `src/devops_cli/commands/gh.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/github/rate_limit_view.py`, `src/devops_cli/github/branch_update.py`, `src/devops_cli/git/operations.py`.
- Test files: `tests/invariants/test_pull_request_template.py`, `tests/test_pr_cmd.py`, `docs/TESTING.md`.

## Feasibility

- On `origin/main` 6c502854, `commands/gh.py:1280-1370` contains `_format_reset_time`, `_parse_rate_limit_payload`, and `_format_rate_limit_rows`.
- `commands/pr.py:1586-1660` contains `_plan_update_all_prs` and `_open_prs_argv`.
- `commands/repos.py:205-235` contains `_extract_url_path` and `_parse_clone_destination`.
- `tests/test_pr_cmd.py:956-985` contains template assertions on `.github/pull_request_template.md`.
- `tests/support/fakes/github.py` and `tests/support/fakes/process.py` provide the shared fakes for GitHub and process execution.
