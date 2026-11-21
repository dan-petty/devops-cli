# Design

## Decisions
- **The App's network git child uses `github_token()`.**: That call raises `GitHubUnauthenticatedError` with the mint's reason, as for a gh child. The job then stops with the cause in its log.
- **A person's git child keeps its no-token start.**: A person can use a credential helper or a public remote, so the remote gives the answer.
- **A failed lookup is not kept.**: Each later call looks again. No retry loop, wait or cap is added.

## Rejected alternatives
- **Keep the 60 second window and log the failure.**: Rejected: git still runs with no token, and the remote's error hides the cause.
- **Retry the mint in a loop.**: Rejected: #5529 showed a delay on the GitHub side after a good mint, and a retry of the mint does not fix that.
