# Task 705: Correct Secondary-Limit Backoff and Retry-After Handling in `run_gh`

**Issue**: [#705](https://github.com/dan-petty/devops-cli/issues/705)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/cli`, `priority/p0-critical`

---

## 1. Description & Objectives

`run_gh` (`src/devops_cli/github/rate_limiter.py`) is the centralized `gh` seam, with quota-derived pacing, a read cache, and an automated retry loop. Previously, `calculate_backoff_delay` never checked whether remaining quota reached zero: whenever a future reset epoch was tracked, it waited until the primary reset epoch regardless of remaining quota. On secondary rate limits, it lacked a floor, and `Retry-After` headers were ignored.

This implementation delivers PR1 (P0):
- Classifies primary limits (`remaining == 0`), secondary rate limits, and server `Retry-After`.
- Waits for the primary reset epoch only on primary limit exhaustion (`remaining == 0`).
- On secondary rate limits, enforces a configured floor (`DEFAULT_GH_SECONDARY_RATE_WAIT = 60.0`), followed by tenacity `wait_random_exponential` bounded by `DEFAULT_GH_SECONDARY_MAX_CAP = 300.0`.
- Returns server `Retry-After` unchanged without local cap clamping.
- Supports `DEFAULT_GH_MAX_RATE_LIMIT_WAIT` (`max_rate_limit_wait`), raising `GitHubRateLimitError` stating the wait and reset time when exceeded.
- Persists `total_throttles` and `total_wait_seconds` in `_global` metadata on disk and displays them in `devops gh rate-limit` (both table and JSON formats).
- Declares `tenacity` in `pyproject.toml` and updates `AGENTS.md`.

---

## 2. Deliverables & Checklist

- [x] Declare `tenacity==9.1.4` in `dependencies` in `pyproject.toml` and lock in `uv.lock`.
- [x] Define `CONST_GITHUB_SECONDARY_RATE_LIMIT_PATTERNS` and add `retry-after` patterns to `CONST_GITHUB_RATE_LIMIT_PATTERNS` in `src/devops_cli/config/constants.py`.
- [x] Define `DEFAULT_GH_SECONDARY_RATE_WAIT = 60.0`, `DEFAULT_GH_SECONDARY_MAX_CAP = 300.0`, `DEFAULT_GH_MAX_RATE_LIMIT_WAIT = None` in `src/devops_cli/config/defaults.py` and export in `src/devops_cli/config/__init__.py`.
- [x] Implement `extract_retry_after`, `_handle_retry_after_wait`, `_is_primary_exhausted`, `_calculate_primary_delay`, and `_calculate_secondary_delay` helpers in `src/devops_cli/github/rate_limiter.py`.
- [x] Update `calculate_backoff_delay` to strictly differentiate primary reset (`remaining == 0`), server `Retry-After` (unchanged), and secondary floor + exponential backoff under local cap.
- [x] Persist `total_throttles` and `total_wait_seconds` in `_global` disk quota metadata and record throttles during rate-limit pauses in `_handle_attempt_backoff`.
- [x] Display `Rate Limiter Activity` in `devops gh rate-limit` table format and include `total_throttles` and `total_wait_seconds` in JSON output.
- [x] Align `AGENTS.md` instructions under `Zero Bare gh Invocations` and `Honoring HTTP 429 & Secondary Limits`.
- [x] Unit and integration tests with structural tuple equality assertions in `tests/test_github_rate_limiter.py` and `tests/test_gh_cmd.py`.
- [x] 100% pass across Gated CI quality gates (`uv run devops ci`).

---

## 3. Verification & Results

- `uv run pytest tests/test_github_rate_limiter.py tests/test_gh_cmd.py`: 98 passed.
- `uv run pytest tests/test_architectural_invariants.py`: 13 passed.
- `uv run devops scan complexity src/devops_cli/github/rate_limiter.py`: Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ fully compliant across all functions.
