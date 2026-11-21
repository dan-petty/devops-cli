# Design

## Decisions
- **The App's network git child uses `github_token()`.**: That call raises `GitHubUnauthenticatedError` with the mint's reason, as for a gh child. The job then stops with the cause in its log.
- **A person's git child keeps its no-token start.**: A person can use a credential helper or a public remote, so the remote gives the answer.
- **Only a refusal halts the Service.**: The classifier already gives `GitHubUnreadError` for a 5xx and for no answer, and `identity_refused` reads only `GitHubUnauthenticatedError`. So the mint raises the error of the classifier, and the Service needs no change.
- **A failed renewal uses the kept token.**: The token is valid until it expires, so a short failure stops no call. Renewal stays due, so each call mints again, and a warning log says that the renewal failed. The log holds no text of the mint, because the mint also gives the token; the request metric keeps its status.
- **A failed lookup is not kept.**: Each later call looks again. No retry loop, wait or cap is added.

## Rejected alternatives
- **Keep the 60 second window and log the failure.**: Rejected: git still runs with no token, and the remote's error hides the cause.
- **Retry the mint in a loop.**: Rejected: #5529 showed a delay on the GitHub side after a good mint, and a retry of the mint does not fix that.
