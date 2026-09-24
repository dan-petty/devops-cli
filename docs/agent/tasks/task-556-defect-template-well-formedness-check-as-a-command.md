# Task 556: Defect Template Well-Formedness Check as a Command

**Issue**: [#556](https://github.com/dan-petty/devops-cli/issues/556)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

Templates were verified by hand for #503, #504 and #537: every site applied to the pinned samples and checked with tree-sitter, gcc, g++, node, `bash -n`, python-hcl2, PyYAML and a block-comment tracker. That caught nginx's control-flow checksum, Hugo code shortcodes and JSDoc injections, and should run whenever a template or sample changes.

#### Key Deliverables:
- Context & Rationale*: Templates were verified by hand for #503, #504 and #537: every site applied to the pinned samples and checked with tree-sitter, gcc, g++, node, `bash -n`, python-hcl2, PyYAML and a block-comment tracker. That caught nginx's control-flow checksum, Hugo code shortcodes and JSDoc injections, and should run whenever a template or sample changes.
- Deliverable*: A command sweeping the templates over the fetched samples: sites per template and category, mutations that no longer parse with each installed checker, and sites inside comments; missing checkers reported as not run; each sweep saved in the run store and comparable with the last.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
