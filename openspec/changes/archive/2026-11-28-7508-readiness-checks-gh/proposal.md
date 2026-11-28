# Proposal

## Why

The merge-readiness verdict of `devops pr ready`, `devops pr check-readiness` and `devops pr monitor` reads the check runs and the commit statuses of the head commit through REST, and removes the older runs of each check itself. When the head reports no check, it reads each workflow file at the head and copies the branch and path filters of GitHub to guess whether a check can start. `devops pr checks` falls back to the same REST reads when `gh pr checks` fails. This code broke in #5144, #5383 and #5408, and `gh pr checks` already does the read (#7508, a part of #7499).

## What Changes

- The verdict reads the checks with `gh pr checks <n> --repo <repo> --json name,state,bucket,workflow,link`, and judges each check that gh lists with the bucket of gh.
- When gh answers `no checks reported`, the verdict reads the rules of the base branch. Rules that require a check keep the pending stand-in. Rules that require no check give the no-CI advisory, so `pr ready` and `pr monitor` do not wait. A read of the rules that fails keeps the pending stand-in.
- `devops pr checks` reads `gh pr checks --json` only. A failed read fails closed with exit 1 and names the cause.
- Delete `src/devops_cli/github/workflow_triggers.py` and its tests, `GitHubClient.pull_request_workflow_at`, `read_commit_checks` and the REST read of the commit statuses in `check_verdict.py`, the REST fallback of `fetch_pr_check_verdicts`, `_render_pr_checks_fallback` (no caller), the message `ready_no_ci` (a copy of `readiness_no_ci`) and the dependency `wcmatch`.
- The output and the exit codes of the three commands change for a repository with no CI, so the change carries a spec delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge-readiness`: the verdict reads the checks with `gh pr checks`, and the rules of the base branch replace the guess from the workflow triggers.
- `review-workspace`: `devops pr checks` has no fallback, so it reads no origin of a checkout.

## Impact

- Code: `src/devops_cli/github/check_verdict.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/client.py`, `src/devops_cli/github/pr_plans.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`; `src/devops_cli/github/workflow_triggers.py` is deleted.
- Tests: `tests/github/test_merge_readiness.py`, `tests/github/test_pr_check_verdict.py`, `tests/commands/test_pr.py`, `tests/commands/test_pr_cmd.py`, `tests/commands/test_pr_dry_run.py`; `tests/github/test_workflow_triggers.py` is deleted.
- Dependencies: `pyproject.toml` and `uv.lock` lose `wcmatch`.
- Documents: the generated command reference.

The change fits one pull request. #7509 moves the poll loop of `pr monitor`, #7510 the check reads of the roadmap rows, and #7512 the template pull request of `repos onboard`.

## Feasibility

- gh v2.106.0 is in the devcontainer: the build info of `/usr/local/bin/gh` holds `github.com/cli/cli/v2 v2.106.0`. The runner image copies the same binary from the devtools image (`Dockerfile:199`).
- `pkg/cmd/pr/checks/checks.go` at v2.106.0: with `--json`, gh prints the list and exits 0. A head with no check returns the error `no checks reported on the '<branch>' branch`, which gh prints as one line on stderr with exit 1 (`internal/ghcmd/cmd.go`, `printError`). `pkg/cmd/pr/checks/aggregate.go` (`eliminateDuplicates`) keeps the newest run of each check and of each status context, and sets the bucket.
- On 2026-11-28, `GET /repos/dan-petty/devops-cli/rules/branches/main` holds a `required_status_checks` rule with Static Analysis, Tests & Coverage and Semantic PR title. `read_required_check_names` reads that endpoint for `branch_update.py` and `release/merge_candidate.py` already.

## Existing Tool Considered

GitHub CLI (https://github.com/cli/cli), MIT, v2.106.0 (2026-11-25). It reads the check runs and the commit statuses of the head, keeps the newest run of each check and gives the bucket. It holds no project policy, so the verdict keeps the pending stand-in, the no-CI rule over the rules of the base branch, and the fail-closed blockers. The deleted internal code is in What Changes.
