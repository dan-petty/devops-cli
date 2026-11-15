# Proposal: #5020

## Why
Three separate code paths open a draft pull request: `stage.py`, `implement_run.py`, and `commands/pr.py`.
Labels and status are applied inconsistently across these call sites.
A crash between branch push and pull request opening leaves an orphaned remote branch.
This change consolidates all draft pull request opening and updating into one module `src/devops_cli/roadmap/steps/open.py` and one command `devops roadmap step open`.
Closes #5020.

## What Changes
- Add `src/devops_cli/roadmap/steps/open.py` with `open_or_update(request)` and sweep recovery.
- Add CLI command `devops roadmap step open` in `src/devops_cli/commands/roadmap_step_open.py` and register in `src/devops_cli/commands/roadmap_step.py`.
- Add `find_open_pull` method in `src/devops_cli/github/client.py`.
- Refactor `src/devops_cli/roadmap/stage/stage.py` and `src/devops_cli/roadmap/implement/implement_run.py` to call `open_or_update`.
- Add architectural invariant test ensuring only `steps/open.py` calls `create_draft_pull`.

## Capabilities
- `roadmap-stage/open`: Unified pull request opening, field diffing, label synchronization, and recovery.

## Impact
- All roadmap jobs open and update pull requests through one shared implementation.
- No duplicate pull requests are created on repeated runs.

## Feasibility
- GitHub pulls API provides `head` and `base` branch filtering.
- Validated with unit tests using `GitHubApiFake`.

## Existing Tool Considered
- GitHub REST API pulls endpoint with head and base filters, through gidgethub.
