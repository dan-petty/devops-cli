# Task 521: A Shipped Release Closes Its Epic While the Roadmap Header Lags

**Issue**: [#521](https://github.com/dan-petty/devops-cli/issues/521)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/release`, `priority/p2-medium`

---

## 1. Description & Objectives

Release epic #297 stayed open after v0.2.22 shipped on 2026-09-22 with its tag, GitHub release
and closed milestone. All 20 of its deliverable issues had closed as completed, but the epic
still read "Deliverable Progress: 3/20" and "Status: Active Release".

- `devops release epic` closed an epic only when the roadmap section header said `Completed`.
  The header is edited by hand, and the v0.2.22 release PR (#335) marked v0.2.21 Completed but
  left v0.2.22 at "Active Release", while v0.2.23, the release in progress, read "Scheduled".
- Eight v0.2.22 entries (#317, #319, #321–#326) were unticked, although their issues closed as
  completed through PRs #361–#391.

### Key Deliverables Completed:

- [x] **Shipped means completed**: the epic sync reads the repository's closed milestones and
  treats a release whose milestone is closed as completed, so its epic closes and renders as
  Completed even when the roadmap header lags.
- [x] **Roadmap corrected**: v0.2.22 is Completed, v0.2.23 is the active release, and the eight
  delivered entries are ticked with the PR that delivered each.
- [x] **#297 closed**: `devops release epic v0.2.22` updated the epic to 20/20 (100%) and
  closed it as completed.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_release_epics.py`: a release whose milestone is closed while its header reads
    "Active Release" has its epic updated to Completed and closed.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
