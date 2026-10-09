# Task: Agent Feasibility Check & Stop Guidelines (#1348)

**Issue**: [#1348](https://github.com/dan-petty/devops-cli/issues/1348)
**Status**: Done
**Milestone**: v0.2.33
**Priority**: priority/p1-high
**Scope**: type/docs, scope/agent, priority/p1-high
**Feasibility**: Verified AGENTS.md workflow structure, task file validation rules, and roadmap store API for returning items.

## Description
Adds explicit feasibility check instructions to AGENTS.md and the instruction generator before coding. When an item cannot be built as specified, the agent writes no compensating code, comments on the issue with evidence, returns the item to New via `devops roadmap return` (with `--dry-run` support), and stops. Updates the task-file template to include a Feasibility line, enforced by `tests/test_agent_task_files.py` on all new task files.

## Acceptance Criteria
- [x] AGENTS.md and instruction generator add a feasibility check before any code: confirm premise against real system, and say in the task file how it was checked.
- [x] When an item cannot be built as specified, the agent writes no compensating code, comments on the issue with evidence, returns the item to New (`devops roadmap return --comment "<evidence>" --confirm`, which supports `--dry-run`), and stops.
- [x] AGENTS.md lists the four signals to stop rather than add code: swallowing an error, product code that detects tests, a second fix on top of a fix in the same area within one release, and a review loop that keeps finding new defects in the same feature.
- [x] The task-file template gets a "Feasibility" line, and `tests/test_agent_task_files.py` requires it on new task files.
- [x] `changelog.d/1348.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.

## Deliverables
- [x] Added `devops roadmap return` command with `--comment`, `--comment-file`, `--dry-run`, `--confirm`.
- [x] Added `ReturnPlan`, `plan_return`, `apply_return`, `dry_run_return`, `render_return_plan` in `src/devops_cli/roadmap/return_item.py`.
- [x] Updated `AGENTS.md` and `instruction_generator.py` with feasibility check and stop signals.
- [x] Updated `docs/agent/tasks/README.md` template with `**Feasibility**` field.
- [x] Enforced `**Feasibility**` on new task files in `tests/test_agent_task_files.py`.
- [x] Unit test suite in `tests/test_roadmap_return.py`.
- [x] Changelog fragment `changelog.d/1348.md`.
