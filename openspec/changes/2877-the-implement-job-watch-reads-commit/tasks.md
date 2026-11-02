# Tasks

## 1. Pass a check reader through the merge-readiness verdict and the monitor

Reads: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/github/check_verdict.py`, `tests/github/test_merge_readiness.py`. Changes: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/pr_monitor.py`, `tests/github/test_merge_readiness.py`.

- [ ] 1.1 In `tests/github/test_merge_readiness.py`, a test passes a `checks` reader to `assess_merge_readiness` and asserts that the verdict calls it and not `read_commit_checks`, and verify that `uv run devops ci test tests/github/test_merge_readiness.py` fails on the base
- [ ] 1.2 Add a `checks` keyword to `assess_merge_readiness`, defaulting to `read_commit_checks`, and carry it in `_Reads`. `_judge_checks` calls `reads.checks(...)`. Add the same keyword to `get_pr_monitoring_status` and `monitor_pr` in `src/devops_cli/github/pr_monitor.py`, and pass it to `assess_merge_readiness`, and verify that `uv run devops ci test tests/github/test_merge_readiness.py` passes

## 2. Read check runs only in the implement watch

Reads: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/github/check_verdict.py`. Changes: `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_implement_pull.py` (new).

- [ ] 2.1 In the new `tests/roadmap/test_roadmap_implement_pull.py`, a test replaces `monitor_pr` in `devops_cli.roadmap.implement_pull` and asserts that `watch_pull` calls it with `checks=read_check_runs`, and that `read_commit_checks` is never called, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_pull.py` fails on the base
- [ ] 2.2 `watch_pull` passes `checks=read_check_runs` to `monitor_pr`, importing `read_check_runs` from `devops_cli.github.check_verdict`. The test doubles `monitor_pr` and the clock, and asserts the call, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_pull.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
