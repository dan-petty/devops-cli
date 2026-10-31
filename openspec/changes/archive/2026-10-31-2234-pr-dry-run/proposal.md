# Proposal

## Why

Issue #2234: The owner dry-run rule states that a dry run makes no external request. External requests include GitHub API calls, child processes, and network sockets. A dry run returns planned requests and the real result type. Seventeen `pr` commands currently do not follow this rule: they make external requests through `gh` or `GhCliClient` without returning an ordered request plan.

## What Changes

- Add `--dry-run` option where missing and `@dry_run_class("request-plan")` to the 17 `pr` commands:
  - `pr check-readiness`
  - `pr checks`
  - `pr close`
  - `pr create`
  - `pr diff`
  - `pr edit`
  - `pr hardening-report`
  - `pr list`
  - `pr monitor`
  - `pr ready`
  - `pr threads list`
  - `pr threads reply`
  - `pr threads resolve`
  - `pr threads resolve-all`
  - `pr threads unresolve`
  - `pr view`
  - `pr wait`
- Implement argument builders and request planners for these commands returning ordered `PlannedRequest` sequences without external network or child-process calls.
- Render request plans through `render_request_plan` or emit structured JSON dictionaries when JSON format is requested.
- Remove all 17 commands from `tests/fixtures/dry_run_gaps.json`.
- Add test coverage in `tests/github/test_pr_dry_run.py` verifying request-plan accuracy, absence of external requests, and structured JSON output.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-dry-run-class`: add dry-run request plans and classifications for 17 `pr` commands.

## Impact

- Users and agents running `devops <command> --dry-run` or `devops --dry-run <command>` inspect planned requests safely.
- No network requests or child processes execute during dry-run mode.
- All 17 commands pass the ratchet invariant test.

## Feasibility

- Premise confirmed: all 17 commands exist in `src/devops_cli/commands/pr.py` and are listed in `tests/fixtures/dry_run_gaps.json`.
- `PlannedRequest` and `render_request_plan` exist and format command plans cleanly.
- Tests obey the test floor with no subprocess or network access.

## Existing Tool Considered

Reuses existing `PlannedRequest` and `render_request_plan` primitives from `devops_cli.dry_run.requests`.
