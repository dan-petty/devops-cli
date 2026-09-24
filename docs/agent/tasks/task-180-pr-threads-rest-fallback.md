# Task 180: REST API Fallback & Rate Limit Handling for PR Review Threads

**Issue**: [#180](https://github.com/dan-petty/devops-cli/issues/180) / [#189](https://github.com/dan-petty/devops-cli/issues/189)
**Status**: Done
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/github`

---

## 1. Description & Architectural Objectives

Resolve the unhandled `GitHubOperationError: GitHub GraphQL query failed: gh: API rate limit already exceeded for user ID ...` crash in `devops pr threads list` and `devops gh issues` commands by introducing resilient, automatic REST API fallback and graceful error degradation.

### Key Objectives
1. **Adaptive REST API Fallback in `list_pr_review_threads`**:
   - Catch GraphQL rate limit errors (`API rate limit already exceeded`, `rate limit`, HTTP 429, secondary rate limits) in `src/devops_cli/github/pr_threads.py`.
   - Implement `fetch_review_threads_rest(owner, repo, pr_number)` that queries `GET /repos/{owner}/{repo}/pulls/{pr_number}/comments` with pagination.
   - Aggregate root comments and reply comments into `ReviewThread` models preserving `ReviewComment` threads.
   - Fail closed for `unresolved_only=True` by treating root comments as unresolved threads since REST does not expose thread resolution status.
2. **CLI Error Hardening in `devops pr threads list`**:
   - In `src/devops_cli/commands/pr.py`, catch any unhandled `GitHubOperationError` and exit cleanly with formatted error output (`print_error`) rather than emitting unhandled Python tracebacks.
3. **Graceful REST Fallback in `get_repository_issues`**:
   - In `src/devops_cli/github/issues.py`, detect when `gh issue list --json` fails due to GraphQL rate limits or execution errors.
   - Adaptively fall back to `GET /repos/{owner}/{repo}/issues` using REST API, excluding pull request items, to keep `devops gh issues triage` and `devops gh issues status` functional.
4. **FastMCP & Submodule Testing**:
   - Author unit tests verifying GraphQL rate limit detection, REST fallback thread aggregation, comment reply chaining, and issue query fallback.
   - Maintain cyclomatic complexity $\le 10$ and nesting depth $\le 5$.
   - Pass all `devops ci` quality gates.

---

## 2. Implementation Checklist

- [x] Ground issues [#180](https://github.com/dan-petty/devops-cli/issues/180) and [#189](https://github.com/dan-petty/devops-cli/issues/189) to `status/in-progress`.
- [x] Create topic branch `fix/180-pr-threads-rest-fallback`.
- [x] Author task document `docs/agent/tasks/task-180-pr-threads-rest-fallback.md`.
- [x] Author unit tests in `tests/test_github_pr_threads.py` and `tests/test_github_issues.py` for REST fallback logic.
- [x] Implement REST fallback in `src/devops_cli/github/pr_threads.py`.
- [x] Implement clean error handling in `src/devops_cli/commands/pr.py` (`devops pr threads list`).
- [x] Implement REST fallback in `src/devops_cli/github/issues.py` (`get_repository_issues`).
- [x] Verify test suite and code coverage $\ge 90\%$ (`pr_threads.py` 90%, `issues.py` 91%).
- [x] Validate cyclomatic complexity $\le 10$ and architectural invariants.
- [x] Execute `devops ci` quality gate.
- [ ] Open draft PR and monitor CI checks.
