# Agent Operational Documentation & Task Tracking

This directory contains automated, agent-specific task tracking, operational state, and execution history.

## Structure

- [`task.md`](task.md): Continuous, real-time task status tracking across all operational lifecycles, structured into:
  - **Completed Tasks**: Verified implementations, green test gates, and synchronized documentation references.
  - **In-Progress Tasks (WIP)**: Active focus items, specific files under modification, and ongoing specifications.
  - **Pending Tasks**: Backlog requirements and upcoming milestones.

## Conventions

- All AI coding assistants and automation agents must maintain and update task tracking under `docs/agent/` rather than placing temporary or agent tracking files in the project root.
- References in `AGENTS.md` and `docs/ROUTINE_TASKS.md` reflect `docs/agent/task.md` as the canonical location for agent task tracking.
- AI agents must continuously align `docs/agent/task.md` with GitHub Projects v2 integration (`.github/project-template.json`) via `devops gh project sync --dry-run` and link PRs to tracked issues and roadmap milestones.
