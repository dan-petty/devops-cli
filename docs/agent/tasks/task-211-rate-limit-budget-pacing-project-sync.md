# Task 211: Enforce Window-Budgeted Rate Pacing, Disk Quota Persistence, and Diff-Only Project Sync

**Issue**: [#211](https://github.com/dan-petty/devops-cli/issues/211)
**PR**: [#212](https://github.com/dan-petty/devops-cli/pull/212)
**Status**: In Review
**Milestone**: `v0.2.18`
**Priority**: `priority/p0-critical`
**Scope**: `scope/github`, `scope/cli`

---

## 1. Description & Objectives

The GitHub GraphQL rate limiter previously permitted rapid quota exhaustion (burning 4,376 of 5,000 requests in 20 minutes) due to:
1. Blind sync field mutations in `devops gh project sync` (issuing 5 GraphQL item-edit calls per candidate across 326 candidates = 1,630 mutations per run).
2. Ephemeral rate limiter state losing quota tracking between independent CLI executions.
3. Lack of rate limit response headers on `gh project item-edit`.
4. Window-blind pacing delays that defaulted to 0.5s when quota was >50%.

### Key Deliverables:
1. **Logical Exponential Backoff & Window-Budget Pacing ([`rate_limiter.py`](file:///workspaces/devops-cli/src/devops_cli/github/rate_limiter.py))**:
   - Eliminated arbitrary fixed numeric thresholds and ratio cutoff steps (`low_threshold`, `critical_threshold`, `is_quota_low`, `is_quota_critical`).
   - Continuous exponential backoff based on percentage of quota used vs available:
     $$\rho = \frac{\text{pct\_used}}{\max(0.001, \text{pct\_available})} = \frac{\text{used}}{\max(1, \text{remaining})}$$
     $$\text{delay} = \min\left(60.0,\; \max\left(\text{min\_interval},\; \text{min\_interval} \times 2^{\frac{\rho}{\text{divisor}}}\right)\right)$$
   - Smooth scaling across all resource limits (from 10 to 15,000) from 0% used ($0.50\text{s}$) to 95% used ($21.5\text{s}$) to 99% used ($60.0\text{s}$).
   - Calculate window-budget pacing dynamically: $\text{delay} = \max\left(\text{min\_interval},\; \frac{\text{reset\_epoch} - \text{now}}{\text{remaining}} \times \text{cost\_factor}\right)$.
   - Pacing exemption for rate limit inspections (`_is_rate_limit_check`), preventing `devops gh rate-limit` hangs.
2. **Cross-Process Quota Persistence ([`.data/cache/gh_quota.json`](file:///workspaces/devops-cli/.data/cache/gh_quota.json))**:
   - Persist rate limit metrics to disk and load on startup across independent CLI processes.
   - Pessimistic decrements for headerless GraphQL commands via `decrement_quota_estimate()`.
   - Test isolation via `resolve_quota_cache_path()` honoring `DEVOPS_CLI_DATA_DIR`.
3. **Diff-Only Project Reconciliation ([`projects.py`](file:///workspaces/devops-cli/src/devops_cli/github/projects.py))**:
   - Query existing items and fields in a single cached call (`gh project item-list`).
   - Parse JSON robustly with `extract_json_payload()` to ignore CLI preambles (`Fetching ViewerOwner...`).
   - Extract and normalize fields case-insensitively with `_extract_item_fields()`.
   - Diff intended fields against current values via `_filter_differing_fields()`.
   - Skip field mutations when values already match, reducing steady-state mutations to 0.
   - Eliminated hardcoded circuit breakers; sync operations are governed continuously by window budget pacing and exponential backoff.
4. **No-REST Fallback**:
   - Strictly honor GraphQL quotas and backoff in PR threads and monitor without REST fallbacks.

---

## 2. Verification & Acceptance Criteria

- [x] Cyclomatic complexity $\le 10$ and nesting depth $\le 5$ in `rate_limiter.py` and `projects.py`.
- [x] All 8 architectural invariant tests in `tests/test_architectural_invariants.py` pass.
- [x] All 53 unit tests in `tests/test_github_rate_limiter.py` and `tests/test_github_projects.py` pass.
- [x] All 13 unit tests in `tests/test_github_pr_threads.py` pass.
- [x] `ruff check` and `ruff format --check` report 0 errors.
- [x] Live rate limit verification confirms pacing active and quota preserved.
