# Task 489: Task Files Link Their Issue Only

**Issue**: [#489](https://github.com/dan-petty/devops-cli/issues/489)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/chore`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

Task files carried a `**PR**` field and an `In Review` status. A pull request's number is unknown
until the PR exists, so recording it took a second commit. That commit re-ran every check (CI
triggers on `synchronize`) and was itself a prohibited standalone tracking commit. `In Review`
went stale the moment the PR merged. The files had also drifted: 173 had a `**PR**` line, and
statuses included `In Review`, `Merged`, `Completed`, `Closed…` and `Review / In Progress`. The
project-sync parser read `Merged` and `Closed` as `Backlog`.

A task file now links its issue only. The issue links the pull request that closes it
(`Closes #N`), and project cards take `In Review` from that open pull request (`infer_item_status`).

### Key Deliverables Completed:

- [x] **Format**: `**Issue**` link, and a status of `Backlog`, `Ready`, `In Progress` or `Done`.
  A delivering pull request writes `Done` in the commit that delivers the work.
- [x] **Generator and parser**: the roadmap sync no longer writes `**PR**`. The task parser no
  longer maps anything to `In Review`.
- [x] **Migration**: `**PR**` removed from 173 files. Statuses were set from each issue's GitHub
  state: 105 files whose issues are closed became `Done`, and open issues kept theirs. Eight bare
  `#N` references became links. The one task delivered by a pull request without an issue (#182)
  links that pull request.
- [x] **Instructions**: AGENTS.md and `docs/agent/tasks/README.md` describe issue-only linking,
  and drop the old rule to open a draft, set `In Review` and fill in the `PR` field.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_agent_task_files.py`: every task file links its issue, has no `**PR**` field,
    and uses an allowed status.
  - `tests/test_github_roadmap_sync.py`: generated task files carry no `**PR**` field.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).
