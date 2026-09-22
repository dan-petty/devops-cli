# Task 405: Per-Check Input Scoping for the CI Cache

**Issue**: [#405](https://github.com/dan-petty/devops-cli/issues/405)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

The CI cache is all-or-nothing: a single changed file invalidates every gate, so editing a markdown file re-runs `mypy`, `bandit` and the full test suite. Each gate reads a knowable subset of the tree — `actionlint` reads `.github/workflows`, `ruff` and `mypy` read `src` and `tests`, docs validation reads `docs` and the CLI surface — and a gate whose inputs did not change has already been answered.

#### Key Deliverables:
- Context & Rationale*: The CI cache is all-or-nothing: a single changed file invalidates every gate, so editing a markdown file re-runs `mypy`, `bandit` and the full test suite. Each gate reads a knowable subset of the tree — `actionlint` reads `.github/workflows`, `ruff` and `mypy` read `src` and `tests`, docs validation reads `docs` and the CLI surface — and a gate whose inputs did not change has already been answered.
- Deliverable*: Declare an input glob set per check, fingerprint each set independently, and reuse a cached verdict per check rather than per run. The existing whole-workspace fingerprint becomes the fallback for checks that genuinely read everything.
- Constraint*: A check must fail closed. An input set that under-declares what a gate reads will report a stale pass, which is worse than re-running it, so the mapping needs to be derived from what each tool is actually invoked against rather than assumed.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
