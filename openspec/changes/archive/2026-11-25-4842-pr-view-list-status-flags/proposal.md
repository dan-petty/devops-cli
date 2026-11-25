# Proposal: #4842

## Why

`devops pr view` exposes only `--repo` and `--dry-run`, `devops pr list` exposes only `--state`, `--limit`, `--repo`, and `--dry-run`, and `devops pr status` does not exist. Agents and developers routinely need `--json`, `--jq`, `--comments`, `--search`, `--head`, and `--base`, and `devops gh pr` shares the same application. #4842 forwards those `gh` options from `devops pr` and `devops gh pr`, adds `devops pr status` / `devops gh pr status`, prints raw `gh` output (and `gh` errors without a fallback table) when `--json` or `--jq` is requested, and includes every option in `--dry-run` plans.

## What Changes

- Extend `pr_view_args` and `plan_pr_view` in `src/devops_cli/github/pr_plans.py` with `comments`, `json_fields`, and `jq_expr`; extend `pr_list_args` and `plan_pr_list` with `search`, `head`, `base`, `json_fields`, and `jq_expr`; and add `pr_status_args` and `plan_pr_status`.
- Update `view_pr` (`--json`, `--jq`/`-q`, `--comments`/`-c`) and `list_prs` (`--json`, `--jq`/`-q`, `--search`/`-S`, `--head`/`-H`, `--base`/`-B`) and add `status_pr` (`devops pr status` / `devops gh pr status` with `--json`, `--jq`/`-q`, `--repo`/`-R`, `--dry-run`) in `src/devops_cli/commands/pr.py`.
- Return raw masked stdout (and masked `gh` stderr on non-zero exit without table fallback) when `--json` or `--jq` is passed to `pr view`, `pr list`, or `pr status`.
- Add help strings in `src/devops_cli/lang/en/help.py` and regenerate documentation (`docs/commands/pr.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`).
- Add comprehensive unit and dry-run tests across `tests/commands/test_pr_dry_run.py` and `tests/commands/test_pr_cmd.py`.
- Fits in one pull request.

## Capabilities

### New Capabilities

- `pr-passthrough`: Forward `gh` JSON, jq, comments, search, head, and base options on `pr view`, `pr list`, and `pr status` under both `devops pr` and `devops gh pr` with raw-output mode and zero-execution `--dry-run` plans.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/github/pr_plans.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/commands/pr.md`, `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/commands/test_pr_dry_run.py`, `tests/commands/test_pr_cmd.py`

## Feasibility

- Verified `src/devops_cli/commands/gh.py:143` mounts `pr_app` directly as `devops gh pr`, so commands and flags on `src/devops_cli/commands/pr.py` are exposed at both `devops pr` and `devops gh pr`.
- Verified `src/devops_cli/github/pr_plans.py:23-85` already drives `pr_list_args`/`plan_pr_list` and `pr_view_args`/`plan_pr_view` through `run_gh` and `PlannedRequest`.
- Verified `openspec list --specs` shows no conflicting active change modifying `pr-passthrough` or `gh-command-names`.

## Existing Tool Considered

Uses `cli/cli` (`gh`), already installed and invoked through `run_gh` in `src/devops_cli/github/rate_limiter.py`. Only missing wrapper options, raw-output branching, `pr status` wiring, dry-run plans, and tests are added (~60 lines of wrapper code plus tests, zero new external dependencies, zero code deleted).
