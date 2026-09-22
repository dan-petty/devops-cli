# Task 432: Executable Verification Criteria

**Issue**: [#432](https://github.com/dan-petty/devops-cli/issues/432)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/cli`, `priority/p0-critical`

---

## 1. Description & Objectives

This was scheduled on the premise that personas emit `verification_criteria` as deterministic shell assertions (`git check-ignore -v <path>`, `git ls-files`, `grep -n <symbol> <file>`) which nothing executes. The recorded data does not support that premise. Across 3167 criteria in 59 review sessions, **2 begin with `git`, none with `grep` or `rg`, and one with `python`**; 3069 are prose descriptions of an observable condition, such as "The exception message includes a placeholder or masked host component". An executor built today would execute three criteria out of 3167.

#### Key Deliverables:
- Context & Rationale*: This was scheduled on the premise that personas emit `verification_criteria` as deterministic shell assertions (`git check-ignore -v <path>`, `git ls-files`, `grep -n <symbol> <file>`) which nothing executes. The recorded data does not support that premise. Across 3167 criteria in 59 review sessions, **2 begin with `git`, none with `grep` or `rg`, and one with `python`**; 3069 are prose descriptions of an observable condition, such as "The exception message includes a placeholder or masked host component". An executor built today would execute three criteria out of 3167.
- Deliverable, in order*: First make criteria executable -- constrain the persona prompts and the finding schema so a criterion is either a command from a closed read-only allowlist or is explicitly marked unexecutable. Only then execute them in the bounded subprocess sandbox (`review_environment`), attach the captured output to the finding, and derive confidence from the outcomes.
- Constraint*: The second half is worthless without the first and cannot be tested against real data until it exists. Sequencing them the other way round is what put this at P0 on an assumption nobody measured.
- Already done*: the self-agreement confidence score is removed. `confidence_score` was computed as `len(verified_criteria_matched) / len(verification_criteria)` -- the model's claim about its own criteria, divided by the criteria it wrote -- which is why findings carried 0.95 while being refutable by reading one file. An absent score now stays absent, per the project rule that a score must come from a tool's rating or a structured model response.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
