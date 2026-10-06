# Task: Do Not Move Issues to Backlog If They Have an Open or Merged Pull Request (#1244)

**Issue**: [#1244](https://github.com/dan-petty/devops-cli/issues/1244)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/github, type/feature

## Description

Previously, `devops roadmap reprioritize` demoted any non-critical issue joining the active release milestone after its start to the backlog with the reason `Moved to the backlog: after <release> started, only a critical fix can join it. A person can place it in a planned release, and that placement stands.`. This caused issues with in-flight development or merged PRs (such as #1242 with PR #1243) to be unexpectedly evicted from the active release.

This implementation preserves issues with active or completed pull request implementations:
- **Roadmap Store PR Queries**:
  - `_OPEN_PULL_REQUESTS_QUERY` in `github_store.py` updated from `pullRequests(states: OPEN, ...)` to `pullRequests(states: [OPEN, MERGED], ...)` to index both open and merged pull requests.
  - `MemoryStore.open_pull_requests()` updated to include both `PullRequestState.OPEN` and `PullRequestState.MERGED`.
- **Admission & Descoping Rules (`reprioritize.py`)**:
  - Added `Event.PR_JOINED = "pr_joined"` and `Reason.PULL_REQUEST = "pull_request"`.
  - Added `(_S, Event.PR_JOINED): Transition(Action.ADMIT, Reason.PULL_REQUEST)`, `(_C, Event.PR_JOINED): Transition(Action.ADMIT, Reason.PULL_REQUEST)`, and `(_P, Event.PR_JOINED): Transition(Action.KEEP, Reason.PULL_REQUEST)` to `TRANSITIONS`.
  - Extended `admission_event(item, *, has_pr=False)` to return `Event.PR_JOINED` when an issue is linked to an open or merged PR.
  - Updated `_plan_rules` to pass `has_pr=bool(run.linked_pull_requests(item.number))` into `admission_event`, admitting items with PRs and keeping them in the release.
  - Updated `_rule_event` and `_cap_decisions` so items with linked PRs are treated as started and exempt from over-cap descoping.
  - Updated `_start_event` and `_fill_or_trim` so items with linked PRs are not demoted at release start even if `New` or `Blocked`, and are not trimmed when over cap.
- **Messaging**:
  - Added `"pull_request": "an open or merged pull request is in flight for it."` to `MESSAGES.roadmap.reasons`.

## Acceptance Criteria

- [x] `_OPEN_PULL_REQUESTS_QUERY` queries `states: [OPEN, MERGED]` and `MemoryStore.open_pull_requests()` returns open and merged PRs.
- [x] An issue joining a started release that has an open pull request is admitted (`Action.ADMIT`) and kept in the release.
- [x] An issue joining a started release that has a merged pull request is admitted (`Action.ADMIT`) and kept in the release.
- [x] An issue with an unmerged (closed) pull request is moved to the backlog as before.
- [x] An issue with an open or merged pull request is not descoped as an over-cap victim when a critical fix takes the release over cap.
- [x] A `New` or `Blocked` item with an open or merged pull request stays in the release at release start.
- [x] Full unit and regression test coverage in `tests/test_roadmap_reprioritize.py` and `tests/test_roadmap_github_store.py`.
- [x] `uv run devops ci` passes with 100% checks passing.
- [x] `changelog.d/1244.md` exists and documents the feature.
