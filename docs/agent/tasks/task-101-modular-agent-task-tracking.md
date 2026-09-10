# Task: Modularize Agent Task Tracking to Eliminate Merge Conflicts (#101)

**Issue**: #101
**Status**: Done
**Milestone**: v0.2.15
**Priority**: priority/p1-high
**Scope**: scope/github

## Description
Decompose the monolithic `docs/agent/task.md` file into isolated, per-task markdown tracking files under `docs/agent/tasks/` to eliminate merge conflicts between concurrent feature branches. Task updates are restricted to the context of commits delivering that specific deliverable or PR merge events.

## Acceptance Criteria
- [x] Directory and file parsing tested via unit tests in `tests/test_github_projects.py`
- [x] CLI default for `--task-file` updated to `docs/agent/tasks` in `src/devops_cli/commands/gh.py`
- [x] Per-task tracking files created in `docs/agent/tasks/`
- [x] Zero merge conflicts between concurrent feature branches
- [x] AGENTS.md and ROUTINE_TASKS.md updated with modular task file conventions
- [x] All 10 CI quality gates pass cleanly

## Deliverables
- [x] Decomposed `src/devops_cli/github/projects.py` parser into complexity-compliant helpers (`_is_task_markdown`, `_find_active_task_files_in_dir`, `_resolve_default_task_fallbacks`, `_resolve_task_files`, `_extract_line_status`, `_parse_checklist_items`, `_parse_standalone_task_metadata`).
- [x] Updated `parse_tasks_to_project_items` to natively support directories, single files, and standard fallbacks while excluding README and archive files.
- [x] Updated CLI option `--task-file` / `-f` default to `docs/agent/tasks` in `src/devops_cli/commands/gh.py` and help catalog in `src/devops_cli/lang/en/help.py`.
- [x] Created `docs/agent/tasks/README.md` documenting task file format, naming, and commit context rules.
- [x] Archived historical phases 1-50 into `docs/agent/archive/historical-phases-1-to-50.md`.
- [x] Seeded Milestone v0.2.15 task files (`task-088-*.md`, `task-089-*.md`, `task-090-*.md`, `task-091-*.md`, `task-094-*.md`, `task-099-*.md`, `task-101-*.md`).
- [x] Replaced `docs/agent/task.md` with lean index table pointing to modular task files.
- [x] Updated `AGENTS.md` and `docs/ROUTINE_TASKS.md` to establish the modular task tracking mandate.
