# Task 285: AI Request Priority Classification (Interactive, Regular, As-Available)

**Issue**: [#285](https://github.com/dan-petty/devops-cli/issues/285)
**Status**: Done
**Milestone**: `v0.2.21`
**Priority**: `priority/p1-high`
**Scope**: `scope/ai`, `scope/cli`, `scope/scheduler`

---

## 1. Description & Objectives

Comprehensive implementation of priority classification across AI / LLM client requests and dynamic slot leasing:
- [x] 1. **Priority Taxonomy**: Define `RequestPriority` enum (`HIGH` / interactive, `NORMAL` / regular, `AS_AVAILABLE` / background) with canonical ordering and integer weightings.
- [x] 2. **Priority-Aware Dynamic Slot Leasing**: Enhance `acquire_ollama_slot` in `src/devops_cli/ai/client/network.py` with priority scheduling and reservation headroom so that:
  - `HIGH` priority (chat, interactive CLI, latency-sensitive calls) takes precedence and can preemptively lease slots.
  - `NORMAL` priority (code review, diff analysis, commands) leases available capacity in fair rotation.
  - `AS_AVAILABLE` priority (scheduled tasks, background prewarming, offline jobs) only leases when capacity is available without starving higher-priority queues.
- [x] 3. **Context Variable & Call Propagation**: Provide a Python `ContextVar` (`current_request_priority`) and optional `priority` parameter on `LLMClient.chat`, `LLMClient.complete`, `LLMClient.stream`, etc., defaulting to `HIGH` for interactive chat and `NORMAL` for batch operations.
- [x] 4. **Scheduler & Background Task Integration**: Wire background and scheduled cron / timer jobs to execute under `RequestPriority.AS_AVAILABLE`.
- [x] 5. **Comprehensive Verification & Gated CI**: Author unit tests verifying priority queuing, starvation prevention, and as-available non-blocking execution, passing all Gated CI quality checks.

---

## 2. Verification Results

- **Priority Queue Validation**: Verified that `HIGH` priority requests acquire slots ahead of waiting `NORMAL` and `AS_AVAILABLE` requests.
- **As-Available Non-Blocking**: Validated that background tasks yield to interactive chat workloads without causing Head-of-Line starvation.
- **Gated CI Quality Gate**: `uv run devops ci` passed 100% across all checks with zero failures, zero warnings, and $\ge 90.0\%$ code coverage.
- **Architectural Invariants**: All architectural invariants validated, with cyclomatic complexity $M \le 10$ and depth $\le 5$ project-wide.
