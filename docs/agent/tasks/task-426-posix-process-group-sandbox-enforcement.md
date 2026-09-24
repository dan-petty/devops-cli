# Task 426: POSIX Process Group Sandbox Enforcement

**Issue**: [#426](https://github.com/dan-petty/devops-cli/issues/426)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/cli`, `priority/p0-critical`

---

## 1. Description & Objectives

Enforces POSIX process group containment (`start_new_session=True` on `subprocess.Popen`) and clean termination via `os.killpg` across background dispatchers, eliminating zombie leaks adopted by PID 1.

#### Key Deliverables:
- Context & Rationale*: Enforces POSIX process group containment (`start_new_session=True` on `subprocess.Popen`) and clean termination via `os.killpg` across background dispatchers, eliminating zombie leaks adopted by PID 1.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
