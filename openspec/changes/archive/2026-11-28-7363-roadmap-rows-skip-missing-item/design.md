# Design

## Decisions

- **Store-owned drop and single warning line**: Preserve the `#7337` contract where `GitHubRoadmapStore` drops the stale listing record and logs `#<n> is no issue of <repo> now... The store leaves it out.` once per issue (`_left`), while extending `GitHubRoadmapStore.closures` and `GitHubRoadmapStore.last_renamed_at` (`_read_timeline`) to verify missing GraphQL timelines via `_read_issue` so they drop and log the same way. Give `InMemoryRoadmapStore` a matching `leave(number)` helper that emits the same single warning line and removes the issue on first read or write.
- **Per-item `GitHubNotAnIssueError` guards matched by item number**: In every row (`implement`, `implement_submit`, `stage`, `stage_submit`, `watch`, `open`, `refine`, `retitle`, `fix-plan`, `intake`, `metrics`), catch `GitHubNotAnIssueError` only when `gone.number == item.number` so errors referencing a different issue number still fail the item or round. Never log a second duplicate warning from the row when the store already logged it.
- **Preserve non-item roadmap distinction in `return_item.py`**: Raise `GitHubNotAnIssueError(repo, item_number, operation="roadmap.return")` only when `store.issue(item_number)` is `None` (the issue left the repository); keep `DevOpsCLIError(f"#{item_number} is not an item of the roadmap.")` when an issue still exists in the repo without a `priority/*` label.
- **Close orphan plan pull requests in `plan_drift`**: Catch `GitHubNotAnIssueError` (letting other `GitHubNotFoundError` propagate), call `reads.close_pull(repo, pull.number)`, and write one warning log line.
- **Test 301 on repository name read**: Cover a 301 redirect from `/repos/<old>` to `/repositories/<id>` returning `full_name` in `tests/github/test_github_client_issue_reads.py`.

## Rejected alternatives

- **Catching `GitHubNotFoundError` broadly in rows**: Hides unrelated 404 errors (such as missing comments or files on an existing issue) and prevents propagating non-issue 404s in `plan_drift`.
- **Logging again in every row handler**: Produces duplicate log lines when running with `GitHubRoadmapStore`, breaking the single-log-line invariant of `#7337`.
