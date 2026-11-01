# Proposal

## Why
Issue #2255 addresses the dry-run rule (#412) for config, workspace, openspec, and docs commands. The rule states that a dry run makes no external requests and returns the planned requests that the real run makes. Currently, `config init` makes external GitHub requests without a request plan, 4 commands change local files without `--dry-run` previews, and 17 commands make no external requests and need the `no-external-request` classification (removing legacy echo-only previews).

## What Changes
- Classify `config init` with `@dry_run_class("request-plan")`, adding `--dry-run` and `--json` support to preview external GitHub requests without executing subprocesses or interactive prompts.
- Classify 4 local mutating commands with `@dry_run_class("no-external-request")`, adding `--dry-run` to print local previews without modifying files or keyring:
  - `config set`
  - `workspace add`
  - `workspace generate`
  - `workspace remove`
- Classify 17 commands with `@dry_run_class("no-external-request")`:
  - `config audit-keys` (remove `--dry-run` and echo-only preview)
  - `config audit-stream`
  - `config auth-headless`
  - `config env`
  - `config env-vars`
  - `config get`
  - `config output`
  - `config show`
  - `config unset` (remove `--dry-run` and echo-only preview)
  - `docs check`
  - `docs generate` (remove `--dry-run` and echo-only preview)
  - `docs sync-readme` (remove `--dry-run` and echo-only preview)
  - `openspec archive` (remove `--dry-run` and echo-only preview)
  - `openspec check`
  - `openspec regenerate` (remove `@dry_run_command` and `--dry-run`)
  - `workspace clean` (remove `--dry-run` and echo-only preview)
  - `workspace open`
- Remove all 22 commands from `tests/fixtures/dry_run_gaps.json`.
- Add test coverage across all 22 commands verifying dry run behavior and zero external calls.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `command-dry-run-class`: Add requirements and scenarios specifying request-plan behavior for `config init`, local previews for `config set`, `workspace add`, `workspace generate`, `workspace remove`, and no-external-request execution for the other 17 commands.

## Impact
- Command interfaces: `config init` gains `--dry-run` and `--json`; local mutating commands gain `--dry-run` previews; echo-only `--dry-run` options removed from read-only commands.
- Test suite: `tests/fixtures/dry_run_gaps.json` gap count decreases by 22.
- Documentation: CLI documentation synchronized.

## Feasibility
Confirmed against repository code and upstream rules:
- `config init` checks `run_gh(["auth", "status"])`; in dry run it renders `PlannedRequest("gh", "auth status", argv=("gh", "auth", "status"))` with zero subprocess calls.
- `config set`, `workspace add`, `workspace generate`, and `workspace remove` mutate local files or keyring; dry run prints preview actions and skips mutations.
- The 17 mark-only commands execute locally with zero external network or cluster requests.
- All 22 commands are currently in `tests/fixtures/dry_run_gaps.json`.
- Fits in one pull request.

## Existing Tool Considered
The change uses internal mechanisms `PlannedRequest`, `render_request_plan`, and `@dry_run_class` introduced in #741 and sub-issue 00 (#886). It removes legacy echo-only previews with no backward-compatibility shim.
