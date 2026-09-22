# Task 414: Generator-Side Rule Pruning Measured Against Verifier Overlap

**Issue**: [#414](https://github.com/dan-petty/devops-cli/issues/414)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`, `priority/p2-medium`

---

## 1. Description & Objectives

The shared review prompt carries roughly a dozen host-specific invalidation rules that the verifier prompt also applies to every finding. The duplication costs tokens on every persona and every segment. Removing them is not obviously right: suppressing a false positive at generation time is cheaper than generating it and invalidating it afterwards, and nothing currently measures which way the trade falls.

#### Key Deliverables:
- Context & Rationale*: The shared review prompt carries roughly a dozen host-specific invalidation rules that the verifier prompt also applies to every finding. The duplication costs tokens on every persona and every segment. Removing them is not obviously right: suppressing a false positive at generation time is cheaper than generating it and invalidating it afterwards, and nothing currently measures which way the trade falls.
- Deliverable*: With the benchmark above in place, remove each duplicated rule in turn and measure findings generated, findings invalidated, and total tokens across both stages. Keep the rules whose removal costs more in verification than it saves in generation.
- Constraint*: Depends on the benchmark. Doing this by argument is how the duplication arose.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
