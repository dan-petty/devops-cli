# Proposal

## Why

Issue #2236: The owner dry-run rule states that a dry run makes no external request. External requests include GitHub, Kubernetes clusters, AI models, network endpoints, and child processes that access them. A dry run returns planned requests and the real result type. Commands without external requests can run normally in dry-run mode. Currently, 15 `gh project`, `gh views`, and `gh pages` commands do not obey this rule: 10 commands make external requests with no request plan, and 5 commands make no external request but are blocked by the lazy proxy.

## What Changes

- Add `@dry_run_class("no-external-request")` to the 5 local-only commands: `gh pages verify`, `gh project status`, `gh project template`, `gh views list`, `gh views spec`.
- Add `--dry-run` option and `@dry_run_class("request-plan")` to the 10 request-making commands:
  - `gh pages build`
  - `gh pages builds`
  - `gh pages status`
  - `gh project audit`
  - `gh project link`
  - `gh project list`
  - `gh project sync`
  - `gh project workflows list`
  - `gh views audit`
  - `gh views sync`
- Implement dry-run request builders for these 10 commands returning ordered `PlannedRequest` sequences without making external network or child-process calls.
- Render request plans via `render_request_plan` in CLI output, or return structured dry-run dictionaries when format is JSON.
- Remove all 15 commands from `tests/fixtures/dry_run_gaps.json`.
- Add comprehensive test coverage in `tests/test_gh_project_views_pages_dry_run.py` verifying request-plan accuracy, absence of external requests, and normal execution for `no-external-request` commands.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-dry-run-class`: add dry-run request plans and classifications for 15 `gh project`, `gh views`, and `gh pages` commands.

## Impact

- Users and agents running `devops <command> --dry-run` or `devops --dry-run <command>` on these 10 commands inspect planned requests safely.
- Users and agents running `devops --dry-run <command>` on the 5 local commands execute them safely and receive normal output.
- All 15 commands pass the ratchet test.

## Feasibility

- Premise confirmed: all 15 commands exist in `src/devops_cli/commands/gh.py` and are listed in `tests/fixtures/dry_run_gaps.json`.
- `reconcile_project_cmd` provides a verified reference implementation for `gh project` request planning.
- `PlannedRequest` and `render_request_plan` exist and handle formatting and structured output.
- All tests obey the test floor with no real subprocess or network access.

## Existing Tool Considered

Reuses existing `PlannedRequest` and `render_request_plan` primitives from `devops_cli.dry_run.requests` and `devops_cli.roadmap.request_plan`.
