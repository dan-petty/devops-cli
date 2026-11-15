# Proposal: #5021 refactor(github): one pull request verdict for all monitors

## Why
Four monitors read a pull request, with two verdict codes:
1. The implement Job watch (`implement_pull.py:325 _judge` and `watch_pull`),
2. The row `stage_ready` (`stage_ready.py:127` with `draft_readiness`),
3. The row `pr_conflicts` (`pr_conflicts.py:100`),
4. The CLI monitor `devops pr monitor` (`src/devops_cli/github/pr_monitor.py:617`).

Two separate wrappers mark a draft ready (`implement_pull.py:414` and `pr.py`).
Additionally, #4927 causes the CLI monitor to report ready when a poll reads no checks at all, and #4838 causes the monitor to stop after a single failed read.
A unified pull request verdict function and a single readiness wrapper eliminate divergence across monitors, properly handle empty checks as pending, and retry failed reads.

## What Changes
- Add `src/devops_cli/roadmap/steps/watch.py`: pure function `verdict(state)` that produces `PENDING`, `READY`, `FAILED` (with check name and failure class), `CONFLICT`, `BEHIND`, `THREADS`, `MERGED`, `CLOSED`, or `HEAD_MOVED`. If the head commit message contains `[skip ci]`, it returns no verdict. Provides a blocking watch loop for monitor callers.
- Add `src/devops_cli/roadmap/steps/ready.py`: unified `draft_readiness` and `mark_ready` (`gh pr ready` wrapper) that ensures the remote head matches the expected head SHA before marking ready.
- Add CLI commands `devops roadmap step watch` and `devops roadmap step ready`.
- Refactor `stage_ready`, implement Job watch, `devops pr monitor`, and `devops pr ready` to call the unified step implementations.
- Fix #4927: a poll reading no check returns `PENDING`.
- Fix #4838: a failed read is retried on subsequent polls rather than stopping immediately.
- Add structural architectural invariant ensuring only `steps/ready.py` wraps `gh pr ready`.

## Capabilities
- `roadmap-step-watch`: unified pull request verdict computation and blocking watch.
- `roadmap-step-ready`: centralized verification and transition from draft to ready.

## Impact
- Unifies pull request evaluation across the roadmap pipeline, stage rows, and CLI commands.
- Prevents premature ready transitions when CI has not started or checks have not been reported.
- Improves resilience against transient GitHub API timeouts during PR monitoring.

## Feasibility
- Verified against existing GitHub GraphQL / REST read structures and current monitor workflows.
- Confirmed with owner decision on 2026-11-13 (tracker #5482, Phase 3).

## Existing Tool Considered
- Existing GitHub CLI and GraphQL / REST endpoints are used. No new tools needed.
