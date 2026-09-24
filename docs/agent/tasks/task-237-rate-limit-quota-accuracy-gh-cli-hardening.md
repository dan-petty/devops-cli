# Task 237: Rate Limit Quota Accuracy, Error Propagation, and GitHub CLI Hardening

**Issue**: [#237](https://github.com/dan-petty/devops-cli/issues/237)
**Status**: Done
**Milestone**: `v0.2.19`
**Priority**: `priority/p1-high`
**Scope**: `scope/github`, `scope/cli`

---

## 1. Description & Objectives

This task addresses quota tracking inaccuracies, error masking, and CLI routing in the GitHub subsystem:

1. **Avoid Inaccurate Quota Defaults & Error Masking**:
   - In `_extract_rate_limit_endpoint_response` (`src/devops_cli/github/rate_limiter.py`), ensure `reset_epoch` does not default to `0.0` when missing or unparsed. Raise structured `GitHubRateLimitError` on malformed API payloads or missing resources instead of silently returning inaccurate quota states.
   - In `devops gh rate-limit` (`src/devops_cli/commands/gh.py`), eliminate fabricated fallback values (e.g. defaulting limits and remaining to `5000` or `0`). Render missing metrics as `"-"` and propagate parsing errors cleanly.

2. **Branch Protection Error Propagation**:
   - In `get_remote_branch_protection` (`src/devops_cli/github/branch_protection.py`), distinguish true 404 / "branch not protected" states from actual API errors (such as quota exhaustion, authentication failure, or malformed JSON), raising `GitHubOperationError` on failure rather than returning `None`.
   - In `_apply_remote_protection`, raise `GitHubOperationError` upon non-zero exit codes and capture errors per branch in `sync_branch_protection`.

3. **Route All GitHub CLI Calls Through Rate Limiter**:
   - In `_execute_release_pr` (`src/devops_cli/commands/release.py`), execute `gh pr create` via `run_gh` rather than unthrottled `run_subprocess`.
   - In `core/process.py`, centralize ambient credential injection (`_inject_gh_credentials`) across both `run_subprocess` and `run_subprocess_async` when invoking `CONST_GH_CLI`.
   - Update knowledge base references (`github_cli.md`) to reflect rate-managed execution via `run_gh`.

---

## 2. Key Deliverables

- `src/devops_cli/github/rate_limiter.py`: Quota extraction error handling without `0.0` default.
- `src/devops_cli/commands/gh.py`: Elimination of hardcoded default quotas and error masking in `rate-limit`.
- `src/devops_cli/github/branch_protection.py`: Unprotected branch error predicate and `GitHubOperationError` propagation.
- `src/devops_cli/commands/release.py`: Route PR creation through `run_gh`.
- `src/devops_cli/core/process.py`: Centralized GitHub CLI credential injection in sync/async subprocess callers.
- `tests/test_github_branch_protection.py`: Unit tests for API failure and JSON error propagation.
- `tests/test_release.py`: Test coverage aligned with `run_gh` PR creation dispatch.
