# Task 276: Socratic Inquiry & Knowledge Gap Formulator (`devops ai research socratic`)

**Issue**: [#276](https://github.com/dan-petty/devops-cli/issues/276)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`
**Feasibility**: Verified against `devops_cli.ai.research` module, model gateway seam, and Typer CLI runtime.

---

## 1. Description & Objectives

Emulates metacognitive awareness ("knowing what you don't know"). Proactively analyzes the agent's current state of knowledge for a task to identify gaps, ambiguities, and underspecified contracts.

#### Key Deliverables:
- [x] Structured epistemic models: `KnowledgeGap` (`GAP`, `AMBIGUITY`, `UNDERSPECIFIED_CONTRACT`), `ClarifyingQuestion`, and `CodeLookupInstruction` with associated rationales.
- [x] Socratic inquiry engine `SocraticFormulator` interfacing with LLM client structured output and markdown task prompt `socratic_inquiry.md`.
- [x] Minimal diagnostic probes with bounded questions and code lookups constrained by `--max-probes`.
- [x] Command `devops ai research socratic` supporting table, JSON, YAML, and Markdown output formats.
- [x] Unit and integration test coverage with structural tuple equality assertions in `tests/test_ai_research_socratic.py`.
- [x] Complexity $M \le 10$ and nesting depth $\le 5$ enforced.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).
