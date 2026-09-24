# Task 498: Finding Locations Keep Paths With `+`, `@`, `~` or `%`

**Issue**: [#498](https://github.com/dan-petty/devops-cli/issues/498)
**Status**: Backlog
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/review`, `priority/p2-medium`

---

## 1. Description & Objectives

`canonicalize_finding_location` matches paths with `[a-zA-Z0-9_\-./\\]`. A path outside that class
falls through to a fallback that keeps its first path-like fragment. Every finding on files under
a corpus named `playbooks+core+...` (#415) was saved as `.data/reviews/corpora/playbooks`, with no
file and no lines.

#### Key Deliverables:
- Accept the characters file names legitimately use (`+`, `@`, `~`, `%`) in every location pattern.
- Regression tests for each character, line ranges included.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
