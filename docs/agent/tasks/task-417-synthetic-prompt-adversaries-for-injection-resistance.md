# Task 417: Synthetic Prompt Adversaries for Injection Resistance

**Issue**: [#417](https://github.com/dan-petty/devops-cli/issues/417)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/ai`, `priority/p2-medium`

---

## 1. Description & Objectives

`sanitize_prompt_injection` strips delimiter tags, and reviewed code is attacker-controlled in the general case — this tool is pointed at arbitrary repositories. Nothing tests whether a source file containing crafted instructions can steer a review, and the sanitizer's coverage is asserted by its own unit tests against the patterns its author thought of.

#### Key Deliverables:
- Context & Rationale*: `sanitize_prompt_injection` strips delimiter tags, and reviewed code is attacker-controlled in the general case — this tool is pointed at arbitrary repositories. Nothing tests whether a source file containing crafted instructions can steer a review, and the sanitizer's coverage is asserted by its own unit tests against the patterns its author thought of.
- Deliverable*: A corpus of source files carrying embedded instructions — in comments, docstrings, string literals, filenames — run through the review pipeline with an assertion that the findings describe the code rather than following the embedded text.
- Constraint*: This measures resistance to the attacks in the corpus and says nothing about the ones not in it. The corpus is a regression suite, not a security proof, and reporting it as the latter would be worse than not having it.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
