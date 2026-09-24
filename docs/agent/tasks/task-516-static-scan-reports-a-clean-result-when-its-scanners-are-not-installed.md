# Task 516: Static Scan Reports a Clean Result When Its Scanners Are Not Installed

**Issue**: [#516](https://github.com/dan-petty/devops-cli/issues/516)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

A review prints "Static analyzers completed (0 finding(s) detected)" after naming six analyzers,
when only Bandit is installed. Semgrep, Trivy, kube-linter and Pluto are skipped silently, and
Gitleaks falls back to its built-in patterns. A reader takes that as a clean scan.

#### Key Deliverables:
- State which analyzers ran and which were unavailable, in the console and the session report.
- Record it so benchmarks can tell a clean scan from a skipped one.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
