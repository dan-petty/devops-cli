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
1. **Canonical Adaptive Limiter & Dynamic Window Budget Pacing ([`rate_limiter.py`](file:///workspaces/devops-cli/src/devops_cli/github/rate_limiter.py))**:
   - Consolidated single source of truth in `GitHubAdaptiveLimiter` implementing exponential velocity shaping:
     $$R(x) = R_0 \cdot \exp\left(-k \cdot \left(\frac{1}{Q - x} - \frac{1}{Q}\right)\right)$$
     where $R_0 = \text{burst\_multiplier} \times \frac{Q}{\Delta T}$ is the initial burst velocity, and $k = 1500.0$ shapes the decay curve as remaining tokens $Q - x \to 0$.
   - **Zero Hardcoded Rate-Limit Windows**: Removed all hardcoded window constants (`DEFAULT_GH_WINDOW_SECONDS`). Rate limit windows and remaining seconds derive strictly from live GitHub response headers (`x-ratelimit-reset`, `x-ratelimit-remaining`, `x-ratelimit-limit`) or GraphQL rate limit payloads.
   - **Dynamic Window Duration Learning**: `_derive_window_seconds()` dynamically learns resource window durations from the difference between consecutive reset epochs ($\Delta T = \text{reset\_epoch}_{new} - \text{reset\_epoch}_{old}$) without fixed mappings.
   - **Small-Quota Detection**: Non-standard or 60-second quotas (such as `code_scanning_autofix`, `search`, and `code_search` with limits $\le 100$) default initial window duration to 60.0s rather than 3600.0s until live responses arrive.
   - **Eliminated Fixed Numeric Thresholds**: Removed arbitrary cutoff steps (`low_threshold`, `critical_threshold`). Pacing smoothly glides to 0 rps as tokens deplete.
   - Pacing exemption for rate limit inspections (`_is_rate_limit_check`), preventing `devops gh rate-limit` deadlocks.
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
