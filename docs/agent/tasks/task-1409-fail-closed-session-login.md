# Task: Fail-Closed Job Clone and Change Filter on Session Login Failure (#1409)

**Issue**: [#1409](https://github.com/dan-petty/devops-cli/issues/1409)
**Scope**: scope/github
**Feasibility**: Verified against the GitHub session fake (`GitHubApiFake`) and git clone / change filtering flows in `src/devops_cli/roadmap/run.py`. Verified that when `GET /user` fails (e.g. 401 unauthenticated or transport error), `_get_session_login()` raises without fallback to `"devops-cli"`, clone rows fail with the login error without writing `"devops-cli"` to the repository config, and the change filter fails the round when the store has no actor.

## Description

Previously, `_get_session_login()` in `src/devops_cli/roadmap/run.py` caught all exceptions from `get_github_session().login` and returned a fallback identity string `"devops-cli"`. This violated the fail-closed engineering principle:
1. `ensure_checkout` wrote `"devops-cli"` into `user.name` and `user.email` in the job clone's git configuration, allowing release cuts and automation jobs to commit with a fictitious identity.
2. `_current_actor` used `"devops-cli"` as the filter actor when `store.actor` / `store._actor` was absent, which stopped the filter from matching the actual actor and caused the Service to react to its own writes.
3. `session.login` in `src/devops_cli/github/session.py` previously executed `gh api user --jq .login` via `subprocess.run` rather than utilizing the session's native REST transport (`GET /user`) introduced in #983.

Remediation applied:
- Switched `session.login` in `src/devops_cli/github/session.py` to `self.rest("GET", "/user")`, returning `str(user["login"])`.
- Removed the exception catching and fallback to `"devops-cli"` in `_get_session_login()`, allowing errors to propagate directly to callers.
- In `ensure_checkout`, failed login lookups raise `GitHubOperationError` (such as `GitHubUnauthenticatedError`), aborting configuration before any `user.name` is written to the clone.
- In `_fetch_filtered_changes` and `run_due_jobs`, failed login lookups fail closed and abort the round rather than continuing with a fake identity.
- Added comprehensive unit and integration tests in `tests/test_github_session.py` and `tests/test_roadmap_run.py` testing through `GitHubApiFake`.

## Acceptance Criteria

- [x] `_get_session_login` lets a failed login lookup raise, with no fallback.
- [x] Clone rows fail closed when login lookup fails, and `user.name` is never written as `"devops-cli"`.
- [x] `_current_actor` caller (`run_due_jobs` / `_fetch_filtered_changes`) fails the round when the actor is absent and login lookup fails.
- [x] Tested through the GitHub session fake (`github_api` / `GitHubApiFake`) refusing `GET /user`.
- [x] Each test call phase stays under 1 s, and `uv run devops ci` passes.
- [x] Changelog fragment `changelog.d/1409.md` records the change.

## Deliverables

- [x] Updated `src/devops_cli/github/session.py` to route `login` through `self.rest("GET", "/user")`.
- [x] Updated `src/devops_cli/roadmap/run.py` to remove fallback in `_get_session_login()`.
- [x] Updated `tests/test_github_session.py` to verify `session.login` caching and error propagation with `GitHubApiFake`.
- [x] Updated `tests/test_roadmap_run.py` to test fail-closed behavior of clone rows and change filtering.
- [x] Added `docs/agent/tasks/task-1409-fail-closed-session-login.md`.
- [x] Added `changelog.d/1409.md`.
