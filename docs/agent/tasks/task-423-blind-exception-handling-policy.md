# Task 423: Blind Exception Handling Policy

**Issue**: [#423](https://github.com/dan-petty/devops-cli/issues/423)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

501 `BLE001` sites exist across `src/`, of which 77 are `except Exception: pass`. Some are legitimate best-effort cleanup; the problem is that nothing distinguishes those from the ones swallowing a defect, and a handler that has never been entered is indistinguishable from one that works. A handler in the workbench of the companion `vibes` repository referenced an undefined name and could only ever raise `NameError`; it survived precisely because no test forced the branch.

#### Key Deliverables:
- Context & Rationale*: 501 `BLE001` sites exist across `src/`, of which 77 are `except Exception: pass`. Some are legitimate best-effort cleanup; the problem is that nothing distinguishes those from the ones swallowing a defect, and a handler that has never been entered is indistinguishable from one that works. A handler in the workbench of the companion `vibes` repository referenced an undefined name and could only ever raise `NameError`; it survived precisely because no test forced the branch.
- Deliverable*: Enable `BLE001`, triage the surface, and require every retained blind handler to carry an explicit `# noqa: BLE001` with a justification and to narrow its exception tuple where the failure modes are known. Every handler written to degrade gracefully needs a test that forces it.
- Constraint*: Triage before enforcement. Turning the rule on against 501 sites without a policy produces one large suppression commit, which is the same silence with more ceremony.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
