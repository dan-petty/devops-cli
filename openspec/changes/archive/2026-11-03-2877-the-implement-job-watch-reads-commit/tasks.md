# Tasks

## 1. Let the merge-readiness verdict read check runs only

Reads: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/check_verdict.py`, `tests/github/test_merge_readiness.py`, `tests/commands/test_pr.py`. Changes: `src/devops_cli/github/merge_readiness.py`, `tests/github/test_merge_readiness.py`.

- [x] 1.1 In `tests/github/test_merge_readiness.py`, two tests call `_assess` with `commit_statuses=False` while `_STATUS` answers HTTP 403. The first asserts that a passed check run gives a ready verdict whose `checks.items` are the check run items, and that `github.gh_sent()` holds no `/status` call. The second asserts that a failed check run blocks as failing, and verify that `uv run devops ci test tests/github/test_merge_readiness.py` fails on the base
- [x] 1.2 Add the keyword `commit_statuses: bool = True` to `assess_merge_readiness` and the field `commit_statuses` to `_Reads`. `_judge_checks` calls `read_commit_checks` as now when it is true, and `read_check_runs(owner, repo_name, head_sha, session=reads.session)` when it is false, and verify that `uv run devops ci test tests/github/test_merge_readiness.py` passes

## 2. Read check runs only in the implement watch

Reads: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/github/pr_monitor.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_timeouts.py`, `tests/commands/test_pr.py`. Changes: `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_implement_pull.py` (new).

- [x] 2.1 In the new `tests/roadmap/test_roadmap_implement_pull.py`, two tests use the `job_world` fixture, make `PullFake` answer the route `/status` with exit 1 and HTTP 403, and call `watch_pull(STAGE_REPO, PULL, head)`. The first, with a passed check run, asserts `WatchKind.READY` and no `gh` call that holds `/status`. The second, with `pull.runs = [[FAIL]]`, asserts `WatchKind.FAILED` and no `gh` call that holds `/status`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_pull.py` fails on the base
- [x] 2.2 Add the keyword `commit_statuses: bool = True` to `get_pr_monitoring_status` and `monitor_pr`, pass it on to `assess_merge_readiness`, and pass `commit_statuses=False` from `watch_pull`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_pull.py` passes

## 3. Say in the workflow document that the watch reads check runs only

Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/implement_pull.py`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 3.1 In the line "After the push" of `docs/ROADMAP_WORKFLOW.md`, add that the watch reads check runs only, because the App token holds no `statuses` permission, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
