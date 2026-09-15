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

#### Key Deliverables:
1. **Canonical Limiter & Dynamic Window Budget Pacing ([`rate_limiter.py`](file:///workspaces/devops-cli/src/devops_cli/github/rate_limiter.py))**:
   - Clean, robust window-budgeted rate pacing calculation: $\text{delay} = \frac{\Delta T_{\text{reset}}}{\text{remaining}}$.
   - **No-Delay Threshold (`DEFAULT_GH_NO_DELAY_USED_PERCENT = 25.0`)**: Under 25% quota utilization, requests incur 0.0s delay for maximum velocity during routine workloads.
   - **Quota Exhaustion Safety**: When remaining requests reach 0, delay scales to the full time until reset, preventing quota overshoot.
   - **Zero Hardcoded Rate-Limit Windows**: Removed all hardcoded window constants. Windows and remaining durations derive dynamically from live GitHub response headers (`x-ratelimit-reset`, `x-ratelimit-remaining`, `x-ratelimit-limit`) and GraphQL rate limit payloads.
   - **Preflight & Inspection Exemption**: Rate limit inspections (`_is_rate_limit_check`) are exempt from pacing delays to avoid self-deadlocks.
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
4. **Mandatory Pre-Push Quality Gate**:
   - Configured `.pre-commit-config.yaml` with `default_install_hook_types: [pre-commit, pre-push]`.
   - Added `devops-ci-pre-push` hook running `uv run devops ci` automatically on `git push`.
   - Hardened `AGENTS.md` instructions forbidding `git push` without prior local passing CI.
5. **Dedicated Project Automation Workflow ([`.github/workflows/project-automation.yml`](file:///workspaces/devops-cli/.github/workflows/project-automation.yml))**:
   - Decoupled GitHub Projects v2 automation and card synchronization from the heavy CI quality gate.
   - Excluded `ready_for_review` trigger from [`.github/workflows/ci.yml`](file:///workspaces/devops-cli/.github/workflows/ci.yml) to eliminate redundant test matrices.
   - Project lifecycle events run lightweight synchronization via `devops gh project sync` in seconds.

---

## 2. Verification & Acceptance Criteria

- [x] Cyclomatic complexity $\le 10$ and nesting depth $\le 5$ in `rate_limiter.py` and `projects.py`.
- [x] All 8 architectural invariant tests in `tests/test_architectural_invariants.py` pass.
- [x] All 53 unit tests in `tests/test_github_rate_limiter.py` and `tests/test_github_projects.py` pass.
- [x] All 13 unit tests in `tests/test_github_pr_threads.py` pass.
- [x] All 76 tests in `tests/test_pr_cmd.py` pass.
- [x] Pre-push hook automatically validates `devops ci` prior to `git push`.
- [x] Full local CI (`uv run devops ci`) passes 10/10 quality gates.
- [x] All remote GitHub Actions CI checks on PR #212 (`Validation`, `Analyze (python)`, `Analyze (actions)`, `CodeQL`) pass.
- [x] PR #212 marked ready for review with 0 unresolved threads and 0 merge conflicts.
