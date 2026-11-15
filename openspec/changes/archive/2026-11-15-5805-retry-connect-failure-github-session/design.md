# Design

## Decisions

### Retry connect failures in `SessionGitHubAPI._request`
Extend `_LOST_CONNECTION` in `src/devops_cli/github/session_transport.py` to include `httpx2.ConnectError` and `httpx2.ConnectTimeout`. Because `lost_connection_wait` already checks `if method != "GET" or attempt > DEFAULT_GH_MAX_RETRIES: return None`, GET requests are resent up to `DEFAULT_GH_MAX_RETRIES` times with jittered backoff on the identity ledger, while write requests (POST) are never resent and immediately raise `GitHubUnreadError`.

### Amend ADR 0006 in place
Add a dated Status History line to `docs/adr/0006-github-session-requests-go-through-gidgethub.md` recording the amendment by the owner decision in #5805 for section Retries. Keep the body text unchanged so `body-hash` remains valid.

### Update spec deltas for `github-session-retry` and `github-session-timeouts`
- In `github-session-retry`: Remove the requirement that a refused connect is sent once. Add requirements that a GET is resent after a connect failure and that a write is not resent after a connect failure.
- In `github-session-timeouts`: Add requirements specifying that a GET that times out on connect is resent up to the retry bound, while a write is not resent.

## Rejected alternatives

### Transport-level `retries` parameter on `httpx2.AsyncClient`
Rejected because transport-level retries resend all methods indiscriminately (including POST) and do not respect the identity rate limiter or ledger throttle.

### Retry loop inside caller or intake store
Rejected because callers across the application would each need duplicate retry loops, whereas the session transport provides a single shared path for all GitHub REST reads.
