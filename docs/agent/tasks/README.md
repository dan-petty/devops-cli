# Modular Agent Task Tracking (`docs/agent/tasks/`)

This directory contains modular, per-task tracking documents for active deliverables, features, bug fixes, and refactoring initiatives.

## Motivation & Architecture

Historically, a monolithic `docs/agent/task.md` file was used for task tracking across branches. When multiple feature branches ran concurrently, each appended lines to the same index table, causing frequent merge conflicts upon PR merge. To eliminate merge conflicts and enable clean multi-agent / multi-branch collaboration, `docs/agent/task.md` has been completely decommissioned and task tracking is decomposed into **isolated, per-task files**:

1. **Zero Merge Conflicts**: Each topic or feature branch creates and edits **only its dedicated task file** (`docs/agent/tasks/task-<issue>-<slug>.md`). Because git treats distinct files independently, merging branches introduces zero conflicts. The one exception: a PR that changes a rule every task file follows brings the existing task files into line in that same PR.
2. **Decommissioned Monolithic Index**: Centralized task visualization, roadmap tracking, and sprint management are managed natively through GitHub Projects v2 (`https://github.com/dan-petty/devops-cli/projects`) and GitHub Issues views (`https://github.com/dan-petty/devops-cli/issues/views`). No central index markdown file is maintained.
3. **Commit Context Rule**: Updates to task tracking files **MUST ONLY** occur in the commit that delivers the feature or fix. One issue is one pull request, which closes the issue and changes its task file. Standalone task-tracking commits, including follow-ups that only add a pull request number, are strictly prohibited. A box is ticked only for work that is done. Work that was not done is a plain bullet naming its follow-up issue. A check only a person can run is a plain bullet starting `Pending a person:`, followed by the exact commands. Verification is the PR's passing checks, which `devops pr check-readiness` reads; typed pass counts and coverage figures are not required.
4. **Issue-Only Linking**: A task file links its GitHub issue and nothing else. The issue links the pull request that closes it (`Closes #<issue>`), and GitHub shows that pull request on the issue. Task files never carry a pull request number or a review state: the number is unknown until the pull request exists, so recording it takes a second commit that re-runs every check.
5. **Project Synchronization**: `devops gh project sync` (and FastMCP `gh_project_sync`) creates or updates the board from `.github/project-template.json` and reconciles Status and Priority on the cards already on it from GitHub. It adds no card, since `devops roadmap intake` places issues and a pull request gets no card, and it does not read task files: the board owns Status, and task files are the implementation record.

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
**Scope**: <scope/*>
**Feasibility**: <How the premise was confirmed against the real system (upstream docs, library source, cluster)>

## Description
<Concise technical description of the deliverable and architectural goals>

## Acceptance Criteria
- [x] <Criterion met, with the test or command that shows it>
- Pending a person: <the exact commands a person runs, and what they should see>

## Deliverables
- [x] <Deliverable done>
- <Work not done>: moved to #<follow-up issue>
```

---

## Lifecycle States

A task file is written only in the pull request that delivers the item (never before implementation). Task files carry no status, milestone, or priority lines: status, milestone, and priority live exclusively on GitHub (Projects v2 and Issues per ADR 0001). `tests/test_agent_task_files.py` enforces that a task file links its issue, has no PR field, has no Status, Milestone, or Priority lines, and has no unchecked boxes (`- [ ]` or `* [ ]`) outside fenced code blocks.

---

## Archival & Historical Records

Completed task files stay in `docs/agent/tasks/` as records. `docs/agent/archive/` holds the older records that were compacted before the per-task files.
