# Proposal

## Why

Issue #2235: The owner dry-run rule states that a dry run makes no external request. External requests include GitHub API calls, Kubernetes clusters, AI models, network endpoints, and child processes that access them. A dry run returns planned requests and the real result type. Currently, 16 `gh issues`, `gh labels`, `gh milestones`, `gh runs`, `roadmap run`, and `survey` commands do not obey this rule: they make external requests without returning an ordered request plan.

## What Changes

- Add `--dry-run` option where missing and `@dry_run_class("request-plan")` to the 16 external-request commands:
  - `gh issues create`
  - `gh issues edit`
  - `gh issues list`
  - `gh issues status`
  - `gh issues triage`
  - `gh labels audit`
  - `gh labels list`
  - `gh labels sync`
  - `gh milestones close`
  - `gh milestones edit`
  - `gh milestones list`
  - `gh milestones status`
  - `gh runs list`
  - `gh runs view`
  - `roadmap run`
  - `survey`
- Implement dry-run request builders for these 16 commands returning ordered `PlannedRequest` sequences without making external network or child-process calls.
- Render request plans through `render_request_plan` in CLI output, or return structured dry-run dictionaries when format is JSON.
- Remove all 16 commands from `tests/fixtures/dry_run_gaps.json`.
- Add test coverage in `tests/test_gh_issues_milestones_labels_runs_dry_run.py` verifying request-plan accuracy, absence of external requests, and structured JSON output.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-dry-run-class`: add dry-run request plans and classifications for 16 `gh issues`, `gh labels`, `gh milestones`, `gh runs`, `roadmap run`, and `survey` commands.

## Impact

- Users and agents running `devops <command> --dry-run` or `devops --dry-run <command>` on these 16 commands inspect planned requests safely.
- No network requests or child processes execute during dry-run mode.
- All 16 commands pass the ratchet invariant test.

## Feasibility

- Premise confirmed: all 16 commands exist in the codebase and are listed in `tests/fixtures/dry_run_gaps.json`.
- `PlannedRequest` and `render_request_plan` exist and handle formatting and structured output.
- All tests obey the test floor with no real subprocess or network access.

## Existing Tool Considered

Reuses existing `PlannedRequest` and `render_request_plan` primitives from `devops_cli.dry_run.requests` and `devops_cli.roadmap.request_plan`.
