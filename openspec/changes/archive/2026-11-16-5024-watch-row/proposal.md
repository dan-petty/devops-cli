# Proposal: #5024

## Why
No row watches plan and delivery pull requests after their producer ends and routes their state. `stage_ready` reads each plan draft every 3 minutes with no backoff (#3671). `pr_conflicts` reads each ready delivery pull request every 19 minutes and only comments. One status-lane row `watch` replaces `stage_ready` and `pr_conflicts` to observe all open roadmap pull requests with single-query batching and route their lifecycle steps. Closes #5024.

## What Changes
- Add the `watch` row to `STATUS_LANE_ROWS` in `src/devops_cli/roadmap/run.py`.
- Remove `stage_ready` and `pr_conflicts` rows from `run.py`.
- Implement `due_steps(state)` pure routing function in `src/devops_cli/roadmap/steps/watch.py`.
- Implement the `watch` status-lane row in `src/devops_cli/roadmap/watch_row.py` using GraphQL with REST fallback during quota holds.
- Implement the watch ledger `{pr, head, verdict, next_read_at}` with 30-minute backoff for failed heads.
- Update documentation in `docs/ROADMAP_WORKFLOW.md` and `k8s/README.md`.

## Capabilities
- `roadmap-watch-row`: Status-lane row watching open roadmap pull requests, batching queries via GraphQL, caching failed heads, and routing lifecycle steps via `due_steps`.

## Impact
- Decreases GitHub API request consumption by batching open pull request status checks into one GraphQL query per repository tick.
- Prevents repeated polling of failed heads within 30 minutes unless head or base branch moves.
- Consolidates separate draft readiness and conflict tracking rows into a single watcher.

## Feasibility
- Tested against the GitHub GraphQL API and existing `verdict` logic from #5021.
- Replaces existing `stage_ready` and `pr_conflicts` adapters without breaking service lane scheduling.

## Existing Tool Considered
- GitHub GraphQL API and REST API with conditional ETag caching via `gidgethub`.
