# Modular Agent Task Tracking (`docs/agent/tasks/`)

This directory contains modular, per-task tracking documents for active deliverables, features, bug fixes, and refactoring initiatives.

## Motivation & Architecture

Historically, a monolithic `docs/agent/task.md` file was used for all task tracking across branches. When multiple feature branches ran concurrently, each appended lines to the same sections, causing frequent merge conflicts upon PR merge.

To eliminate merge conflicts and enable clean multi-agent / multi-branch collaboration, task tracking is decomposed into **isolated, per-task files**:

1. **Zero Merge Conflicts**: Each topic or feature branch creates and edits **only its dedicated task file** (`docs/agent/tasks/task-<issue>-<slug>.md`). Because git treats distinct files independently, merging branches introduces no conflicts.
2. **Commit Context Rule**: Updates to task tracking files **MUST ONLY** occur in the context of the commits delivering the feature/fix, or when merging/closing the PR. Standalone task-tracking commits are strictly prohibited.
3. **Automated Project Synchronization**: `devops gh project sync` (and FastMCP `gh_project_sync`) natively inspects `docs/agent/tasks/` and synchronizes all task cards into GitHub Projects v2.

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

**Issue**: #<issue_number>
**PR**: #<pr_number>
**Status**: <Backlog | Ready | In Progress | In Review | Done>
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

Task statuses align with GitHub Projects v2 and Kanban board views:
- **Backlog**: Queued deliverable, awaiting assignment or active milestone start.
- **Ready**: Scoped with concrete acceptance criteria and tests designed.
- **In Progress (WIP)**: Active work item currently being authored. If an early PR is opened to share work, it must be a Draft Pull Request (`--draft`).
- **In Review**: Pull Request opened and marked ready for review (or converted from draft via `gh pr ready`), with automated review and CI running.
- **Done**: Pull Request merged, remote CI checks green, and issue closed.

---

## Archival & Historical Records

When a release milestone is finalized, completed task files may be compacted into `docs/agent/archive/` or retained as release artifacts. Active directory scans via `devops gh project sync` automatically exclude `README.md` and any files containing `archive`.
