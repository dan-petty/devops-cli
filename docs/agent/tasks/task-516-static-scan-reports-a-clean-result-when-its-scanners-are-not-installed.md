# Task 516: Static Scan Reports a Clean Result When Its Scanners Are Not Installed

**Issue**: [#516](https://github.com/dan-petty/devops-cli/issues/516)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

A review prints "Static analyzers completed (0 finding(s) detected)" after naming six analyzers,
when only Bandit is installed. Semgrep, Trivy, kube-linter and Pluto are skipped silently, and
Gitleaks falls back to its built-in patterns. A reader takes that as a clean scan.

### Key Deliverables Completed:

- [x] **Each analyzer's part is known**: before reporting, the pipeline records how each of the
  six analyzers took part in the review:
  - ran;
  - used built-in patterns (Gitleaks without its binary);
  - not installed;
  - had no files of its kind (no Python for Bandit; no YAML for Kube-linter and Pluto; no
    Dockerfile or lockfile for Trivy).
- [x] **Console**: "Static analyzers completed (N finding(s) detected)" is replaced by the
  analyzers that ran and their findings, and a separate line naming those not installed. When
  none ran, it says so.
- [x] **Session report**: `review.md` has a Static Analyzers table with each analyzer's result.
- [x] **Benchmarks**: `profile.json` records the states, and a benchmark summary keeps every state
  each analyzer had across its runs. `devops review benchmark` prints them, so runs that
  differ show more than one state.
- [x] **Gitleaks' binary** comes from `BIN_GITLEAKS`, like the other scanners.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_static_analyzers.py`:
    - the states for a host with only Bandit;
    - the console lines, including when nothing ran;
    - the reported review end to end (console, orchestrator state and profile);
    - the report table;
    - profile round trip, benchmark merge and benchmark output.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification

On this devcontainer, which has Bandit only, as in the report:

```text
    ✓ Static analyzers found 0 finding(s): Bandit, Gitleaks (built-in patterns) ran
    ! Not installed, so not run: Kube-linter, Pluto, Trivy, Semgrep
```

The unused `stages/static_scan.py` still prints the old message and never calls Trivy. It is one
of six review stage entry points the pipeline never calls, filed for removal as #530.
