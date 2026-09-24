# Task 515: Review Prompts Apply This Repository's Rules to Every Project

**Issue**: [#515](https://github.com/dan-petty/devops-cli/issues/515)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

From the #509 audit. The shared prompts carry several of this repository's rules: its Python version rules, network exemptions, house style rules and roadmap mandates. They also require linked context that the generation prompt never supplies, and keep lockfiles out of review. Build files and templates are reviewed as documentation.

#### Key Deliverables:
- Project rules come from the target's conventions file for persona review and verification alike, and the verifier receives those conventions. The verifier prompt's devops-cli assumptions (`mypy --strict`, internal connectors, console output) move there, and absence rules match the context actually given. Lockfiles and build files are reviewed as what they are. Checked against the multi-language samples (#505).
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
