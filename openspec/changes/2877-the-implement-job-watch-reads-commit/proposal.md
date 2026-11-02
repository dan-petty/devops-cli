# Proposal

## Why

Issue #2877: the implement job watches the checks of its pull request through `watch_pull`. The watch reaches `read_commit_checks`, which also sends `GET /repos/{owner}/{repo}/commits/{ref}/status`. GitHub lists that endpoint under the permission "Commit statuses: read". The installation token of the Service holds no `statuses` permission. When GitHub refuses the call, the read fails closed and the job stops the item with "GitHub could not say whether the checks passed." The stop is a `ci_infra` failure, whose default action is one retry, and a refused permission fails again on each retry. The repository sets no commit status, so the call has no use.

## What Changes

- `assess_merge_readiness` takes a keyword `commit_statuses: bool = True`, and `_Reads` carries it. `_judge_checks` calls `read_commit_checks` when it is true, as it does now. It calls `read_check_runs(owner, repo_name, head_sha, session=reads.session)` when it is false.
- `get_pr_monitoring_status` and `monitor_pr` take the same keyword and pass it to the verdict.
- `watch_pull` passes `commit_statuses=False`, so the implement job watch reads check runs only and sends no request to the commit status endpoint.
- Tests: the verdict with `commit_statuses=False`, and the whole watch through `watch_pull` with a commit status endpoint that refuses.
- `docs/ROADMAP_WORKFLOW.md` says that the watch reads check runs only.
- The change carries a spec delta in `roadmap-implement-job`: what the job reads from GitHub is a service's behavior, which `openspec/config.yaml` calls observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: the watch reads check runs and no commit status

## Impact

- Code: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/github/pr_monitor.py`, `src/devops_cli/roadmap/implement_pull.py`
- Tests: `tests/github/test_merge_readiness.py`, `tests/roadmap/test_roadmap_implement_pull.py` (new)
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Left as they are, on purpose: `devops pr monitor` (`src/devops_cli/commands/pr.py:737`), `devops pr ready` (`:1298`) and `devops pr check-readiness` (`:1640`) keep the default and read commit statuses with the token of a person. `fetch_pr_check_verdicts` (`src/devops_cli/github/check_verdict.py:462`, called by `devops pr checks` at `src/devops_cli/commands/pr.py:387` and `:454`) is not part of the watch. `read_commit_checks` stays, so no name is removed or renamed. `src/devops_cli/roadmap/stage_ready.py:108` already calls `read_check_runs`. The failure class of a stop for unread checks (`src/devops_cli/roadmap/failure.py`, test `tests/roadmap/test_roadmap_failure.py:179`) stays `ci_infra`, because a check run read can still fail.

## Dependencies

- #2865 added `read_check_runs`. It is in the tree: `src/devops_cli/github/check_verdict.py:374`. Nothing to wait for.
- #3103 asks for a commit status `service-vetted` on the head of a Service pull request. After this change the implement watch neither waits for that status nor fails on it. A person merges the pull request after the status passes, so the watch has no need to read it. If #3103 must hold the Job, it posts a check run, which the watch reads.
- #2585 edits `merge_readiness.py` (an advisory for the body of a pull request) and #3049 edits the ready mark in `implement_run.py`. Neither edits `_judge_checks`, `get_pr_monitoring_status`, `monitor_pr` or `watch_pull`. No issue or pull request asks to park, to wait for, or to change the same lines. I searched open issues and pull requests for `2877`, `commit status`, `statuses permission`, `watch_pull`, `pr_monitor`, `monitor_pr` and `merge_readiness`.

## Feasibility

Checked on `origin/main` ff9ad065 with the commands below. Each premise has its output.

- The endpoint needs the permission. GitHub's source for its table "Permissions required for GitHub Apps" (`docs.github.com` itself was not reachable from this session) is `src/github-apps/data/fpt-2022-11-28/server-to-server-permissions.json` in `github/docs`. Fetched from `raw.githubusercontent.com`, key `statuses` reads `"title": "Commit statuses"`, and its first entry reads `"requestPath": "/repos/{owner}/{repo}/commits/{ref}/status", "access": "read", "server-to-server": true`. The key `checks` lists `"requestPath": "/repos/{owner}/{repo}/commits/{ref}/check-runs", "access": "read"`.
- The token holds no such permission. `src/devops_cli/config/constants.py:1412-1419` reads `CONST_GITHUB_APP_TOKEN_PERMISSIONS = {"issues": "write", "pull_requests": "write", "contents": "write", "checks": "read", "actions": "read", "metadata": "read"}`.
- A refusal stops the item. On the unchanged tree I added a scratch test that made the fake of `gh` answer the route `/status` with exit 1 and `gh: Resource not accessible by integration (HTTP 403)`, then ran `watch_pull("example/roadmap-fixture", 5, <head>)` in the job world of `tests/support/roadmap_implement.py`. It printed `Watch(kind=<WatchKind.STOPPED: 'stopped'>, reason='GitHub could not say whether the checks passed.', check=None)` and one call to `/status`. I did not see the real refusal: no App token exists here, and I did not check whether GitHub refuses a token without `statuses` for a public repository. The call has no use in either case.
- The repository sets no commit status. `git grep -n -i "statuses:\|/statuses\|commit-status" -- .github` printed nothing. `gh api repos/dan-petty/devops-cli/commits/8aa72cff026a449cd1256583ab983a7f884ee0f6/status --jq '{state, total_count, statuses: (.statuses|length)}'` printed `{"state":"pending","statuses":0,"total_count":0}` for a head that has 18 check runs.
- The chain to the call. `git grep -n "read_commit_checks"` over `src/` gives `merge_readiness.py:239` (the only call in the verdict) and `check_verdict.py:509`. `watch_pull` calls `monitor_pr` (`implement_pull.py:94`), `monitor_pr` calls `get_pr_monitoring_status` (`pr_monitor.py:643`), and that calls `assess_merge_readiness` (`pr_monitor.py:540`). `implement_run.py:671` and `:678` call `watch_pull`.
- The two readers differ. `read_check_runs(owner, repo_name, head_sha, *, session=None)` is at `check_verdict.py:374-380` and takes no `runner`. `read_commit_checks(owner, repo_name, head_sha, *, runner=run_gh, session=None)` is at `:395-402`. The design uses this fact.
- The change works. In a scratch clone I made the three edits of What Changes (+22 lines, -7 lines), and the scratch test passed with them and failed without them. `uv run pytest` over `tests/github/test_merge_readiness.py`, `tests/commands/test_pr.py`, `tests/roadmap/test_roadmap_implement_timeouts.py` and `tests/roadmap/test_roadmap_implement_job.py` printed `165 passed`. I reverted the edits.
- The other callers keep their test. The helper `_unread` (`tests/commands/test_pr.py:382`) makes the `/status` read fail with HTTP 500. The scenario `checks-unread` (`:425`) expects "check verification failed closed" from `check-readiness`, and `test_pr_monitor_exits_on_the_verdict_once_the_checks_settle` (`:463`) expects exit 1 from `pr monitor`. `tests/github/test_merge_readiness.py:442` asserts the same for the verdict.
- An existing test of the watch does not cover the call. `tests/roadmap/test_roadmap_implement_timeouts.py:150` replaces `monitor_pr` with a stub. It proves the keywords that the watch passes, not the read. No test file for `implement_pull.py` exists, so the new test file is `tests/roadmap/test_roadmap_implement_pull.py`.

## Existing Tool Considered

`read_check_runs` in `src/devops_cli/github/check_verdict.py` covers the need: it reads check runs only and fails closed. A library does not help. PyGithub and gidgethub call the same endpoint with the same permission. The other option is to grant `statuses: read` to the App. It needs no code, but a person must change the App, the token would hold a permission that nothing uses, and `CONST_GITHUB_APP_TOKEN_PERMISSIONS` states what the jobs use. So the change builds a keyword only, not a reader. Cost to build and test: about 35,000 tokens and about 1 hour of elapsed time. Cost to keep: one boolean through three functions and three tests, about 3,000 tokens at the next change of the verdict. Cost to fix: a wrong choice fails a named test. The change deletes no internal code.
