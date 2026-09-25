# Task 557: Backend Activity in Review Profiles and Benchmarks

**Issue**: [#557](https://github.com/dan-petty/devops-cli/issues/557)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

#545's imbalance was measured with a script that sampled `nvidia-smi` and the vLLM queues during
a review. Profiles counted calls per backend, not how long each backend was busy or how many calls
it had in flight at once, so a benchmark could not show whether a routing change spread the load.

### Key Deliverables Completed:

- [x] **Backend activity per stage** (`ai/review/profile.py`). The profiler places each served
  call on its backend's timeline: an observer runs as a call finishes, so the call ran from its
  duration ago until now. Each stage's `activity` records, per backend:
  - `calls`;
  - `busy_seconds`, the union of the calls, so overlapping calls count once;
  - `call_seconds`, their sum;
  - `peak_concurrency`, the most calls in flight at once;
  - `mean_concurrency`, call seconds over busy seconds.

  `StageProfile.busy_share(backend)` is the share of the stage's wall time the backend had a call
  in flight, capped at 1.
- [x] **Benchmark summaries** keep each backend's median busy share and highest peak per stage.
  The `devops review benchmark` table shows them busiest first, for example
  `vllm 60% ×4, ollama-0 10% ×1`. Comparing runs (#555) reads these fields from saved summaries.
- [x] **Direct model requests** report their duration to the spend ledger and its observers, as
  gateway calls already did.
- [ ] **Pool busy share over a window from Prometheus**: moved to #546, since it reads the vLLM,
  gateway and GPU metrics that #546 adds.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_backend_activity.py`:
    - busy time is the union of calls and the peak is their overlap; back-to-back calls do not
      overlap;
    - a profile places each finished call on its backend's timeline by stage, and ignores calls
      with no serving backend;
    - benchmarks take the median busy share and the highest peak;
    - busy share is capped at 1 and is 0 for an idle backend;
    - the benchmark table shows busy share and peak;
    - direct requests report their duration.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
