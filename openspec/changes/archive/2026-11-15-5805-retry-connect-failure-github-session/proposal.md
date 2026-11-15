# Proposal: #5805

## Why
On 2026-11-11, `devops roadmap intake` stopped after 3 minutes 10 seconds because the issue listing read raised `ConnectTimeout`. The same command worked a few minutes later. The GitHub session retries a lost connection, but it does not retry a connect failure. This change resends a GET after `httpx2.ConnectError` or `httpx2.ConnectTimeout`, and it never resends a write.

## What Changes
- Include `httpx2.ConnectError` and `httpx2.ConnectTimeout` in the retried connection errors in `src/devops_cli/github/session_transport.py`.
- Resend a GET after a connect error or a connect timeout up to `DEFAULT_GH_MAX_RETRIES` more times, after the same ledger wait.
- Ensure write requests (such as POST) are not resent after a connect failure and raise `GitHubUnreadError` after one request.
- Update ADR 0006 with a dated Status History entry.
- Update specs `github-session-retry` and `github-session-timeouts`.
- Update tests in `tests/github/test_github_session.py`, `tests/github/test_github_errors.py`, `tests/github/test_github_api_metrics.py`, and `tests/github/test_service_limits.py`.

## Capabilities
- `github-session-retry`: The GitHub session resends a GET after `httpx2.ConnectError` or `httpx2.ConnectTimeout`, while writes are sent once.
- `github-session-timeouts`: The GitHub session resends a GET that times out on connect up to the retry limit, and does not resend a write that times out on connect.

## Impact
- GitHub session reads recover from transient connect errors and connect timeouts.
- Write requests remain safe from duplicate submission.
- ADR 0006 and OpenSpec specifications stay consistent with session retry behavior.

## Feasibility
- Verified existing `SessionGitHubAPI._request` retry loop and `_resend_after_lost` mechanism.
- Verified `httpx2.ConnectError` and `httpx2.ConnectTimeout` are `httpx2.TransportError` subclasses handled by `lost_connection_wait`.

## Existing Tool Considered
No open tool covers the need. `httpx2` transport-level retries cannot differentiate HTTP methods or enforce the identity ledger wait and `DEFAULT_GH_MAX_RETRIES`. Extending the existing `SessionGitHubAPI._request` retry branch covers the requirement at minimal token and maintenance cost.
