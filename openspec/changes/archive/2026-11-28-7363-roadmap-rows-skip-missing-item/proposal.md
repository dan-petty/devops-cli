# Proposal: #7363

## Why

#7337 updated four roadmap paths to skip an item that left the repository and drop its stale record on read or webhook delivery. When no delivery arrives, the remaining roadmap rows (`implement`, `stage`, `watch`, `open`, `refine`, `retitle`, `fix-plan`, `intake`, and `metrics`) still fail one round because reads or writes for the vanished item raise `GitHubNotAnIssueError` (or `LookupError` / `DevOpsCLIError`). In addition, `plan_drift` still catches the wider `GitHubNotFoundError` and leaves orphan plan pull requests open, the GraphQL timeline reads (`closures` and `last_renamed_at`) drop no record when an issue left, and no test covers a 301 redirect when `GitHubClient` reads the repository name.

## What Changes

- Raise `GitHubNotAnIssueError` instead of `LookupError` in `implement_submit._fresh` and instead of bare `DevOpsCLIError` in `return_item.plan_return` / `apply_return` when the issue is gone from the repository.
- Update the item loops of `implement` (`implement.py`, `implement_submit.py`), `stage` (`stage.py`, `stage_submit.py`), `watch` (`watch_row.py`), `open` (`steps/open.py`, `open_row.py`), `refine` (`refine.py`), `retitle` (`retitle.py`), `fix-plan` (`steps/fix_plan.py`), `intake` (`intake.py`), and `metrics` (`github/metrics.py`) to catch `GitHubNotAnIssueError` for the item's own number, record no failure mark or failure class, leave that item out, and continue with the remaining items.
- Handle missing GraphQL timelines in `GitHubRoadmapStore.closures` and `GitHubRoadmapStore.last_renamed_at` so they drop the stale record and raise `GitHubNotAnIssueError`, and support `leave(number)` in `InMemoryRoadmapStore` so row tests exercise single-line logging, record drop, and skip behavior uniformly.
- Narrow `plan_drift` from `GitHubNotFoundError` to `GitHubNotAnIssueError`, close orphan plan pull requests whose issue left with one log line (`DriftReads.close_pull`), and let other `GitHubNotFoundError` errors propagate.
- Add a test in `tests/github/test_github_client_issue_reads.py` verifying that `GitHubClient.get_issue` follows a 301 redirect on the repository name read.

## Capabilities

### New Capabilities

- `roadmap-item-left-other-rows`: Leave out an item that left the repository across the remaining roadmap rows, raise `GitHubNotAnIssueError` in submit/return helpers, drop GraphQL timeline records, close orphan plan pull requests in `plan_drift`, and verify 301 repository name redirects.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/roadmap/implement/implement.py`
- `src/devops_cli/roadmap/implement/implement_submit.py`
- `src/devops_cli/roadmap/return_item.py`
- `src/devops_cli/roadmap/stage/stage.py`
- `src/devops_cli/roadmap/stage/stage_submit.py`
- `src/devops_cli/roadmap/stage/plan_drift.py`
- `src/devops_cli/roadmap/watch_row.py`
- `src/devops_cli/roadmap/steps/open.py`
- `src/devops_cli/roadmap/open_row.py`
- `src/devops_cli/roadmap/refine/refine.py`
- `src/devops_cli/roadmap/retitle.py`
- `src/devops_cli/roadmap/steps/fix_plan.py`
- `src/devops_cli/roadmap/intake/intake.py`
- `src/devops_cli/roadmap/stores/github_store.py`
- `src/devops_cli/github/metrics.py`
- `src/devops_cli/lang/en/messages.py`
- `tests/support/fakes/roadmap_store.py`
- `tests/roadmap/` and `tests/github/` tests

## Feasibility

- `src/devops_cli/roadmap/implement/implement_submit.py:241` raises `LookupError` when `_fresh` sees `None`.
- `src/devops_cli/roadmap/return_item.py:62` raises bare `DevOpsCLIError` when `store.item` returns `None`.
- `src/devops_cli/roadmap/stage/plan_drift.py:261` catches `GitHubNotFoundError` and never closes the pull request.
- `src/devops_cli/roadmap/stores/github_store.py:1481,1499` run GraphQL `_read` directly without `_read_issue` fallback or record drop.
- Each listed row iterates items/pulls without catching `GitHubNotAnIssueError` around per-item reads and writes.

## Existing Tool Considered

None found. The requirements govern internal error handling, GraphQL store drop behavior, and pull request lifecycle logic inside `devops-cli`'s own roadmap subsystem using the existing `GitHubNotAnIssueError` exception.
