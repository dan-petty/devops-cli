# Proposal

## Why

The implement job watch of #2877 reads the checks of its pull request through `read_commit_checks`, which also calls the commit status endpoint. The App token holds no `statuses` permission, so GitHub can refuse the call, the read fails closed, and the job stops the item. The repository sets no commit status, so the call has no use.

## What Changes

- `assess_merge_readiness` takes a `checks` reader, defaulting to `read_commit_checks`, and `_judge_checks` calls it.
- `get_pr_monitoring_status` and `monitor_pr` take the same reader and pass it to the verdict.
- `watch_pull` passes `read_check_runs`, so the implement job watch reads check runs only and never calls the commit status endpoint.
- A new test file `tests/roadmap/test_roadmap_implement_pull.py` asserts that the watch calls `read_check_runs` and not `read_commit_checks`.
- The change carries a spec delta in `roadmap-implement-job`, because the watch of a service is observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The implement job watch reads check runs only

## Impact

- Code: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/roadmap/implement_pull.py`
- Tests: `tests/github/test_merge_readiness.py`, `tests/roadmap/test_roadmap_implement_pull.py`

## Feasibility

- `search_code` for `watch_pull` showed `src/devops_cli/roadmap/implement_pull.py:82` defines it and `src/devops_cli/roadmap/implement_run.py:648` and `:653` call it, so the watch is the implement job's own path.
- `read_file` of `src/devops_cli/roadmap/implement_pull.py:82-106` showed `watch_pull` calls `monitor_pr` and judges its result; it reads no checks itself.
- `read_file` of `src/devops_cli/github/pr_monitor.py:515-565` showed `get_pr_monitoring_status` calls `assess_merge_readiness(pr_data, owner, repo_name, pr_number, runner=runner)` with no session and no check reader.
- `read_file` of `src/devops_cli/github/merge_readiness.py:228-248` showed `_judge_checks` calls `read_commit_checks(owner, repo_name, head_sha, runner=reads.runner, session=reads.session)`, which is the commit status call the issue names.
- `read_file` of `src/devops_cli/github/check_verdict.py` showed `read_check_runs` exists and reads check runs only, and `read_commit_checks` calls `_fetch_commit_statuses_from_rest`.
- `search_code` for `implement_pull` in `tests/` found no test file for the module, so the watch's test is a new file, `tests/roadmap/test_roadmap_implement_pull.py`.
- First checks against the real system: `uv run devops ci test tests/github/test_merge_readiness.py` and `uv run devops ci test tests/roadmap/test_roadmap_implement_pull.py`.

## Existing Tool Considered

The project's own `read_check_runs` in `src/devops_cli/github/check_verdict.py`, added by #2865, reads check runs only and covers the need. The change builds no new reader: it passes that function to the verdict. It deletes no internal code.
