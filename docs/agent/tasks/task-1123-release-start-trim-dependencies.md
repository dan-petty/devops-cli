# Task 1123: Release-Start Trim and Cap Descope Pass Over Dependencies

**Issue**: [#1123](https://github.com/dan-petty/devops-cli/issues/1123)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/github`, `priority/p2-medium`
**Feasibility**: Verified against `reprioritize.py` (_fill_or_trim, _cap_decisions, TRANSITIONS, Event, Reason), `memory_store.py` (link_dependency, dependencies), `lang/en/messages.py`, `tests/test_roadmap_reprioritize.py`, and `tests/test_roadmap_lifecycle_properties.py`.

---

## 1. Description & Objectives

Resolves an issue where `devops roadmap reprioritize` trims a starting release over its cap or descopes a release over its limit in fixed order without considering blocked-by dependencies, which could trim or descope an item while keeping an item that depends on it. The release-start trim and cap descope now repeatedly pick the lowest-ranked unstarted item that no staying item depends on, passing over dependencies needed by staying items.

#### Key Deliverables:
- In `src/devops_cli/roadmap/reprioritize.py`:
  - Add `Event.DEPENDED_ON_AT_START` and `Reason.DEPENDED_ON`.
  - Add `(PLANNED, DEPENDED_ON_AT_START) -> Transition(Action.KEEP, Reason.DEPENDED_ON)` to `TRANSITIONS`.
  - Implement unified victim selection function `_trim_victims` for both `_fill_or_trim` and `_cap_decisions`.
  - Pass over items that staying items depend on, re-evaluating dependencies after each trim.
  - Read blocked-by links (`RoadmapStore.dependencies`) only when a release is over the cap/limit.
  - When a release starts above the cap, name the passed-over items and their dependents in the plan.
- In `src/devops_cli/roadmap/memory_store.py`:
  - Update `link_dependency` to accept optional `repository: str | None = None` and record external repository dependencies.
- In `src/devops_cli/lang/en/messages.py`:
  - Add `depended_on` reason message to `MESSAGES.roadmap.reasons`.
  - Update `trim`, `cap`, and `over_size` reason messages with "...and this was its lowest-ranked unstarted item that no item staying in it depends on."
- In `src/devops_cli/lang/en/help.py` and `src/devops_cli/roadmap/reprioritize.py`:
  - Update command help text and module docstrings stating trim and cap descope follow dependencies.
  - Regenerate docs via `devops docs generate --sync-readme`.
- In `tests/test_roadmap_reprioritize.py`:
  - Update existing trim and descope tests for the new reason messages.
  - Add tests for v0.2.26 shape, started item and critical fix dependencies, cap descope dependencies, mutual cycle starting over the cap, and closed/backlog/cross-repo dependencies.
- In `tests/test_roadmap_lifecycle_properties.py`:
  - Add `dependency` and `above_cap` invariants to the lifecycle machine (total 17 invariants).
  - Update `size` invariant to allow unstarted items depended on by another item in the release.
  - Add gate minimal replay test `test_the_machine_fails_without_the_dependency_trim_rule`.
  - Add `trim-with-dependency` to `SWEPT`.
- Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ maintained.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

## 2. Acceptance Criteria
- [x] Criterion 1: `TRANSITIONS` holds the new row, and one function picks the victims for both `_fill_or_trim` and `_cap_decisions`. `MESSAGES.roadmap.reasons` gains `depended_on`, which names the staying items that depend on the item. The `trim`, `cap`, and `over_size` texts end with "...and this was its lowest-ranked unstarted item that no item staying in it depends on." Help text and module docstring updated and docs regenerated.
- [x] Criterion 2: Blocked-by links are read only when a release is over the cap.
- [x] Criterion 3: Test on in-memory store builds v0.2.26's shape, trims counterparts of #548, #406, #981, and #1083, keeps dependencies, and comments trim reasons. Existing tests pass with updated reasons.
- [x] Criterion 4: Test where started item and critical fix each depend on lowest-ranked unstarted items: trim passes over both dependencies, trims next items, and holds the cap.
- [x] Criterion 5: Test where critical fix joins started release at cap and lowest-ranked item is dependency: fix descopes next item in order.
- [x] Criterion 6: Test with two unstarted items depending on each other: release starts above cap with both items, size is that size, and plan names items that held release above cap and what depends on them.
- [x] Criterion 7: Test where closed dependency, backlog dependency, and cross-repo dependency with same number leave trim order unchanged. `link_dependency` accepts optional repository.
- [x] Criterion 8: Lifecycle machine gains `dependency` and `above_cap` invariants checked after every finished run.
- [x] Criterion 9: Machine's `size` invariant allows unstarted items depended on by another item in release; `test_each_invariant_message_starts_with_a_term_context_md_defines` counts 17 invariants.
- [x] Criterion 10: `test_the_machine_fails_without_the_dependency_trim_rule` verifies Dependency invariant fails without dependency trim rule and passes with it.
- [x] Criterion 11: `trim-with-dependency` scenario joins `SWEPT`, verifying idempotence and stability under faults.
- [x] Criterion 12: In-memory store tests only, no network calls, fast execution, `uv run devops ci` passes.
- Pending a person: record the dependencies named in the open items' "Depends on" lines and the release epics' Ordering sections as GitHub blocked-by links, starting with v0.2.26's (#843 on #832, #981 on #1083, #743 on #982, #744 on #743), so that the store reads them.
- Pending a person: at the next release start over the cap, `uv run devops roadmap reprioritize --dry-run` lists trims, and no kept item depends on any of them.
- [x] Changelog fragment authored at `changelog.d/1123.md`.
