# Proposal: #4626

## Why

The GitHub session reads with the read timeout of the HTTP entry point, `DEFAULT_HTTP_TIMEOUT_SECONDS` (3,600 s), through `session_client` in `src/devops_cli/github/session_transport.py` and `request_timeout` in `src/devops_cli/http/client.py`. That bound is as long as the calls around a GitHub read: the watch of the checks of the implement job polls through the session for at most 3,600 s, and the alternatives unit of #4573 gets a deadline of 3,600 s. When a read gets no answer, the call around it stops at its own deadline before the read fails, and the read error is lost. GitHub ends a REST request after 10 s, so a read that waits longer gets no answer. The owner rule of 2026-11-11 says that each inner timeout is shorter than the call around it. Closes #4626.

## What Changes

- A new default, `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` (60 s), is the read timeout of the GitHub session's client. Only that client uses it.
- The other clients of the HTTP entry point keep `DEFAULT_HTTP_TIMEOUT_SECONDS`, and the release downloads of `devops install-tools` with them.
- A test holds the chain of bounds around a GitHub read: Valkey command 2 s < GitHub session read 60 s < watch of the checks 3,600 s.
- ADR 0006 states the new read bound.

The read bound is a behavior that a consumer observes (a read fails after 60 s, not after an hour), so the change has a spec delta.

## Capabilities

- `github-session-timeouts` (new): the read bound of the GitHub session, the read bound that downloads keep, and the order of the bounds around a GitHub read.

## Impact

- A GitHub read that gets no answer now fails after 60 s with `GitHubUnreadError` naming `ReadTimeout`. Before, it waited up to an hour. The session does not send it again, as before for a read timeout.
- A slow answer is not cut while it arrives: the read timeout is the longest wait for each chunk of data, not for the full body.
- No setting, command or manifest changes. The change fits one pull request.

## Feasibility

- GitHub, "Troubleshooting the REST API" (API version 2026-03-10), read on 2026-11-11: "If GitHub takes more than 10 seconds to process an API request, GitHub will terminate the request and you will receive a timeout response and a "Server Error" message." So no correct answer needs a read of 60 s.
- HTTPX, "Timeouts" page, read on 2026-11-11: the read timeout "specifies the maximum duration to wait for a chunk of data to be received". httpx2 2.13.1 (`uv.lock`) keeps this model, and `request_timeout(read=...)` already takes a read bound.
- Source: `session_client` called `request_timeout(connect=DEFAULT_GH_SESSION_CONNECT_TIMEOUT_SECONDS)`, so the read took the default 3,600 s (`src/devops_cli/http/client.py`, `request_timeout`). `merge_readiness` reads the checks through the session (`get_github_session().client`), and `monitor_pr` polls it up to `roadmap.implement.monitor_timeout_seconds` (3,600 s).
- Source: `_LOST_CONNECTION` in `session_transport.py` holds `RemoteProtocolError`, `ReadError` and `WriteError`, not `ReadTimeout`, so a read timeout is sent once, and `_UNREAD` turns it into `GitHubUnreadError`.
- Test run: a loopback listener that accepts no connection and a read bound of 0.05 s give `GitHubUnreadError` naming `ReadTimeout` after one request.

## Existing Tool Considered

The read timeout of httpx2, which the HTTP entry point already sets through `request_timeout`. No new tool and no new code path: the change passes one more argument. Cost: about 30,000 tokens and 1 hour to build, no upkeep beyond the constant. The change deletes no internal code.
