# Task 339: Eliminate Duplicated Issue Text from Automatic GitHub Issue Reference Expansion in Release Epics

**Issue**: [#339](https://github.com/dan-petty/devops-cli/issues/339)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

In release tracking epics (such as #297), deliverable lines were previously formatted as `- [ ] #<issue_number>: <title> (<priority>, <scope>)`. Because GitHub automatically expands issue references (`#<issue_number>`) in markdown task lists to render the full issue title, issue number, and status badge, including the title alongside the reference caused duplicate issue text on GitHub.

#### Key Deliverables:
- [x] **Root Cause Remediation**: Updated `_format_deliverable_line` in `src/devops_cli/github/release_epics.py` to output `- [{check}] #{item.issue_number}` when `issue_number` is present, leveraging GitHub's native task list issue expansion without redundant text.
- [x] **Fallback Formatting**: Preserved full title, priority, and scope formatting for unlinked items where `issue_number` is None (`- [{check}] {item.title} (\`{item.priority}\`, \`{item.scope}\`)`).
- [x] **Live Epic Synchronization**: Synchronized release epic #297 for milestone `v0.2.22`, verifying clean native task list rendering on GitHub.
- [x] **Testing & Verification**:
  - Updated unit tests in `tests/test_release_epics.py` with structural tuple equality assertions.
  - Maintained cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
  - 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Summary

- **Unit Tests**: 13/13 passed in `tests/test_release_epics.py`.
- **Architectural Invariants**: Complexity check passed ($M \le 10$, nesting depth $\le 5$).
- **Gated CI Quality Gates**: All 10 gates passed locally via `uv run devops ci`.
