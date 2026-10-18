# Task: Task Files Carry No Status, Milestone or Priority (#879)

**Issue**: [#879](https://github.com/dan-petty/devops-cli/issues/879)
**Scope**: scope/docs
**Feasibility**: Verified against docs/agent/tasks/ tree, ADR 0001, and test_agent_task_files.py contract.

## Description

Task files historically carried `**Status**`, `**Milestone**`, and `**Priority**` fields. This metadata led to drift between markdown files and GitHub Projects v2, and created unnecessary administrative commits when updating statuses. Under ADR 0001 ("GitHub is the single source of truth for task status, release milestones, and priority"), task files are solely an implementation record authored by the delivering pull request. This task removes the metadata lines from all task files, deletes unimplemeted task files, updates tests and instructions, and ensures task files are authored exclusively upon delivery.

## Acceptance Criteria

- [x] Removed `**Status**`, `**Milestone**`, and `**Priority**` lines from every task file in `docs/agent/tasks/task-*.md`.
- [x] Deleted every task file whose Status was not `Done` at base (`origin/release/v0.2.37`).
- [x] Updated `tests/test_agent_task_files.py` to enforce that task files link their issue, have no PR field, and have no Status, Milestone, or Priority line; added test verifying forbidden metadata lines raise `AssertionError`.
- [x] Updated `docs/agent/tasks/README.md` to drop metadata fields from template and document that status, release milestone, and priority live on GitHub.
- [x] Updated `AGENTS.md` so no rule asks for a task file before implementation or for a status in it.
- [x] Added deliverable task file and changelog fragment `changelog.d/879.md`.

## Deliverables

- [x] Stripped `**Status**`, `**Milestone**`, and `**Priority**` from 504 existing task files.
- [x] Deleted 36 non-Done task files.
- [x] Contract tests in `tests/test_agent_task_files.py` validating task file fields.
- [x] Updated documentation in `docs/agent/tasks/README.md` and `AGENTS.md`.
