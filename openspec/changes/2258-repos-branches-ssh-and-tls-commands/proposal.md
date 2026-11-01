# Proposal

## Why

Issue #2258 (part of #886) reports that 24 repos, branches, ssh and tls commands do not obey the dry-run rule (#412). Nine make an external request under --dry-run or have no request plan. Fifteen print a generic line or an argument echo instead of running safely. The owner's rule says a dry run makes no external request and returns the requests a real run would make.

## What Changes

- Add the request-plan class and a --dry-run that returns ordered PlannedRequest items to 9 commands (branches sync, branches update, repos clone, repos clone-org, repos sync, repos update, ssh register, ssh rotate, tls enable-k8s).
- Add the no-external-request class to 15 commands (branches clean, branches jira, branches list, repos list, repos worktrees prune, repos worktrees status, ssh audit, ssh generate, ssh list, ssh status, tls ca, tls cert, tls homelab, tls inspect, tls verify).
- Remove echo-only --dry-run previews (render_dry_run_result or @dry_run_command) from the 9 request-plan commands and from ssh list, with no shim.
- Remove all 24 command paths from tests/fixtures/dry_run_gaps.json so the ratchet test passes.
- Write tests that verify no external request is made, the plan matches the real run, and mark-only commands run normally under --dry-run.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-dry-run-class`: request-plan-dry-run-returns-planned-requests, no-external-request-runs-normally, request-plan-matches-real-run

## Impact

- Code: `src/devops_cli/commands/branches.py`, `src/devops_cli/commands/repos.py`, `src/devops_cli/commands/ssh.py`, `src/devops_cli/commands/tls.py`
- Tests: `tests/fixtures/dry_run_gaps.json`, `tests/test_branches_dry_run.py`, `tests/test_repos_dry_run.py`, `tests/test_ssh_dry_run.py`, `tests/test_tls_dry_run.py`, `tests/test_roadmap_dry_runs.py`

## Feasibility

- The premise is confirmed by the #886 inventory (2026-10-25, commit 1bb164bd) and the fixture file tests/fixtures/dry_run_gaps.json, which lists all 24 commands.
- The dry-run infrastructure exists: devops_cli.dry_run.requests.PlannedRequest and render_request_plan are referenced in CHANGELOG.md (#741, #885).
- The test guards in tests/conftest.py (network guard, process guard, keyring deny) are in place and will catch any unfaked external reach.
- The dry-run class decorator and ratchet test come from sub-issue 00, a stated dependency.
- First checks the implementation runs: (1) uv run devops ci test tests/test_roadmap_dry_runs.py to confirm the ratchet test currently fails for these 24 commands; (2) uv run devops branches sync --dry-run to confirm the current generic output; (3) uv run devops ssh list --dry-run to confirm the echo-only preview.

## Existing Tool Considered

The repository already provides devops_cli.dry_run.requests.PlannedRequest, render_request_plan (#741), the dry-run class decorator, and the ratchet test from sub-issue 00. The test guards in tests/conftest.py and the pattern in tests/test_roadmap_dry_runs.py cover the verification. No new dependency is necessary.
