# Modular Agent Task Tracking (`docs/agent/tasks/`)

This directory contains modular, per-task tracking documents for active deliverables, features, bug fixes, and refactoring initiatives.

## Motivation & Architecture

Historically, a monolithic `docs/agent/task.md` file was used for task tracking across branches. When multiple feature branches ran concurrently, each appended lines to the same index table, causing frequent merge conflicts upon PR merge. To eliminate merge conflicts and enable clean multi-agent / multi-branch collaboration, `docs/agent/task.md` has been completely decommissioned and task tracking is decomposed into **isolated, per-task files**:

1. **Zero Merge Conflicts**: Each topic or feature branch creates and edits **only its dedicated task file** (`docs/agent/tasks/task-<issue>-<slug>.md`). Because git treats distinct files independently, merging branches introduces zero conflicts.
2. **Decommissioned Monolithic Index**: Centralized task visualization, roadmap tracking, and sprint management are managed natively through GitHub Projects v2 (`https://github.com/dan-petty/devops-cli/projects`) and GitHub Issues views (`https://github.com/dan-petty/devops-cli/issues/views`). No central index markdown file is maintained.
3. **Commit Context Rule**: Updates to task tracking files **MUST ONLY** occur in the commit that delivers the feature or fix, written as the file should read once merged (`**Status**: Done`). Standalone task-tracking commits, including follow-ups that only add a pull request number, are strictly prohibited.
4. **Issue-Only Linking**: A task file links its GitHub issue and nothing else. The issue links the pull request that closes it (`Closes #<issue>`), and GitHub shows that pull request on the issue. Task files never carry a pull request number or a review state: the number is unknown until the pull request exists, so recording it takes a second commit that re-runs every check.
5. **Automated Project Synchronization**: `devops gh project sync` (and FastMCP `gh_project_sync`) natively inspects `docs/agent/tasks/` and synchronizes all task cards into GitHub Projects v2.

---

## File Naming Convention

Every task file MUST follow the naming standard:

```
docs/agent/tasks/task-<issue_number>-<kebab-case-slug>.md
```

Examples:
- `task-089-k8s-centralized-logging.md`
- `task-090-infracost-finops-cloud-cost.md`
- `task-091-argo-fleet-sync.md`
- `task-099-ci-workflows-cache-optimization.md`

---

## Task File Format Template

Each task file should follow this standard format:

```markdown
# Task: <Feature / Bug / Refactor Title> (#<issue>)

**Issue**: [#<issue_number>](https://github.com/dan-petty/devops-cli/issues/<issue_number>)
**Status**: <Backlog | Ready | In Progress | Done>
**Milestone**: v<version>
**Priority**: <priority/p0-critical | priority/p1-high | priority/p2-medium | priority/p3-low>
**Scope**: <scope/*>

## Description
<Concise technical description of the deliverable and architectural goals>

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Deliverables
- [ ] Deliverable 1
- [ ] Deliverable 2
```

---

## Lifecycle States

A task file records one of four statuses. `tests/test_agent_task_files.py` enforces them, together with the issue link and the absence of a pull request field:
- **Backlog**: Queued deliverable, awaiting assignment or active milestone start.
- **Ready**: Scoped with concrete acceptance criteria and tests designed.
- **In Progress (WIP)**: Active work item currently being authored. If an early PR is opened to share work, it must be a Draft Pull Request (`--draft`).
- **Done**: Written by the delivering pull request, which merges with the work and closes the issue.

Review is not a task-file status. A GitHub Projects v2 card shows **In Review** while the pull request that closes its issue is open and ready for review; `devops gh project sync` derives it from GitHub (`infer_item_status`).

---

## Archival & Historical Records

When a release milestone is finalized, completed task files may be compacted into `docs/agent/archive/` or retained as release artifacts. Active directory scans via `devops gh project sync` automatically exclude `README.md` and any files containing `archive`.
