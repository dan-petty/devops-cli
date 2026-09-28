# Task 555: Evaluation History, Comparison and Regression Checks

**Issue**: [#555](https://github.com/dan-petty/devops-cli/issues/555)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Benchmarks and evaluations are saved in the run store (#554), but comparisons previously
relied on manual diffing of score tables or raw JSON records. A result is only useful over the
life of the tool if subsequent runs can be directly compared against it, setup differences
highlighted, and regression tolerances enforced to gate releases.

### Key Deliverables Completed:

- [x] **Run Store Queries & Retrieval** (`devops_cli/ai/run_store.py`):
  - `get_run(run_id, mechanism=None)` resolves individual run records by ID or prefix from
    local storage or the shared Valkey index.
  - `set_baseline(record)`, `get_baseline(mechanism, subject_key)`, and `list_baselines()`
    persist explicit baseline designations per subject in `<runs_dir>/baselines/` and mirror
    them to Valkey (`INDEX_PREFIX:baseline:<mechanism>:<subject_key>`).
- [x] **Setup Diffing & Metric Comparison** (`devops_cli/ai/run_store.py`):
  - `diff_setup(run_a, run_b)` isolates configuration and environment changes (models, weights,
    page size, pool deployments, concurrency).
  - `compare_runs(run_a, run_b)` computes absolute and percentage shifts across key metrics:
    recall (found and reported), wall time, prompt and completion tokens, and per-backend
    activity and busy share.
  - `check_regression(comparison, tolerances)` validates run results against baseline limits
    (maximum recall drop, maximum latency increase, maximum token increase).
- [x] **CLI Command Surface** (`devops_cli/commands/ai_runs.py`):
  - `devops ai runs list`: tabular or JSON list of historical runs with mechanism and subject filters.
  - `devops ai runs show <run-id>`: formatted view of metadata, setup parameters, and results.
  - `devops ai runs compare <run-id-1> [run-id-2]`: side-by-side metric comparison and setup
    diff; defaults to comparing against the subject's baseline if `run-id-2` is omitted.
  - `devops ai runs baseline set <run-id>`: sets the baseline for a subject.
  - `devops ai runs baseline list`: displays all configured baselines.
  - `devops ai runs check <run-id>`: gates CI / release pipelines, exiting code 1 on regression.
- [x] **Automated Tests & Quality Gates** (`tests/test_run_comparison.py`):
  - List and show runs across mechanisms;
  - Setup diff extraction across changed and identical configurations;
  - Metric comparison (recall, tokens, duration, backend busy share);
  - Baseline setting, retrieval, and default fallback;
  - Regression checking tolerances (pass and failure exits);
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
