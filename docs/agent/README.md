# Agent Operational Documentation & Task Tracking

This directory contains automated, agent-specific task tracking, operational state, and execution history.

## Structure

- [`tasks/`](tasks/README.md): Modular, per-task tracking documents (`task-<issue>-<slug>.md`) providing branch-isolated task state to prevent git merge conflicts across concurrent feature branches.
- [`archive/`](archive/): Compacted historical records and development phases from completed milestone releases.

## Operational Conventions

- **Modular Per-Task Tracking (Zero Merge Conflicts)**: AI agents and topic branches must create and edit only their dedicated task tracking file (`docs/agent/tasks/task-<issue>-<slug>.md`). Modifying shared task files across multiple active branches is strictly prohibited.
- **Commit Context Rule**: Updates to a task file must only be committed in the context of the functional changes delivering that specific task, or when merging the PR into the target release branch. Standalone task-tracking commits are strictly prohibited.
- **GitHub Projects v2 Synchronization**: `devops gh project sync` (or FastMCP `gh_project_sync`) reconciles `Status` and `Priority` on the cards already on the board from GitHub's issue and pull request state and taxonomy labels; it reads no task file and adds no card. New work reaches the board through `devops roadmap intake`, and `Value` and `Effort` are set by hand.
- **Data Isolation**: Operational logs, telemetry traces, and temporary artifacts belong under `.data/agent/` and must never be committed to repository tracking.
