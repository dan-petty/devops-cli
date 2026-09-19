# Task 272: Multi-Scale Semantic Outline & Inspectional Scanner (`devops ai read --inspect`)

**Issue**: [#272](https://github.com/dan-petty/devops-cli/issues/272)
**PR**: None (Draft)
**Status**: Backlog
**Milestone**: `v0.2.21`
**Priority**: `priority/p0-critical`
**Scope**: `type/feature`, `scope/ai`, `priority/p0-critical`

---

## 1. Description & Objectives

Replaces naive monolithic file dumping with human-like inspectional reading and hierarchical perceptual scaffolding. Allows agents to navigate code and documentation across 3 discrete focal zoom levels:

#### Key Deliverables:
- Context & Rationale*: Replaces naive monolithic file dumping with human-like inspectional reading and hierarchical perceptual scaffolding. Allows agents to navigate code and documentation across 3 discrete focal zoom levels:
- Level 0 (Topology)**: AST class/method hierarchies, exported symbols, docstring summaries, and cyclomatic hotspots without function bodies (< 200 tokens/file).
- Level 1 (Structural Outline)**: Function signatures, parameter types, return contracts, and control-flow sketches.
- Level 2 (Deep Focal Window)**: Line-bounded targeted code slices with surrounding breadcrumb context.
- Acceptance Criteria*: Sub-10ms AST outline generation; 85%+ token reduction compared to full-file ingestion; seamless integration with `Stage1PreAnalysis`.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across all 10 CI quality gates (`uv run devops ci`).
