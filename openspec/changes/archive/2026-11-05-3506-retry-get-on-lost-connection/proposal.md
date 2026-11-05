# Proposal

## Why

Issue #3506 asks for a retry of a GitHub read whose connection is lost. A GET that loses its connection fails at once, with no retry. One lost connection then turns a CI job red. It also counts as a failed round of a Service row, which suspends the row sooner. The CI run after 2026-11-04T15:05Z printed `GitHub gave no readable answer to GET /repos/dan-petty/devops-cli/actions/runs/41772844168/jobs?per_page=100: RemoteProtocolError`.

## What Changes

- `src/devops_cli/github/session_transport.py`: `SessionGitHubAPI._request` sends a GET again when its connection is lost. The lost connections are `httpx2.RemoteProtocolError`, `httpx2.ReadError` and `httpx2.WriteError`. For each gidgethub attempt, the session sends the GET at most `DEFAULT_GH_MAX_RETRIES` more times.
- Each resend paces on the ledger of the session's identity. It waits from `DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS`. The wait is recorded as a throttle, as a read 5xx is.
- A write that loses its connection is not sent again. GitHub may have applied it.
- The session does not retry a refused connect, a connect timeout, a read timeout, a proxy error or a local protocol error. The module docstring states this rule.
- `src/devops_cli/github/error_classifier.py`: `refused_retry` accepts a transport error. A transport error has no HTTP status.
- `docs/adr/0006-github-session-requests-go-through-gidgethub.md`: the Retries paragraph states the rule.
- The change adds the spec capability `github-session-retry`. A `devops` command that reads GitHub now sends a lost read again. So the change carries a spec delta.
- The change fits one pull request. It closes #3506 only.
- The change deletes no internal code.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| A `RemoteProtocolError` on the first GET and an answer on the second gives the normal result. | `test_a_get_that_loses_its_connection_is_sent_again` |
| A `RemoteProtocolError` on each attempt ends after `DEFAULT_GH_MAX_RETRIES` retries, and the error stays `GitHubUnreadError` with its present text. | `test_a_get_that_loses_its_connection_on_every_attempt_raises_after_the_retries` |
| A POST that loses its connection sends one request. | `test_a_write_that_loses_its_connection_is_sent_once` |
| A listing that loses its connection on page 3 sends page 3 again and not page 1, and it returns each item once. | `test_a_listing_that_loses_page_3_sends_page_3_again` |
| `httpx2.ConnectError` on a GET sends one request. | `test_no_readable_answer_raises_the_unread_error_without_a_retry[connect-error]` in `tests/github/test_github_errors.py`, kept as the regression test |
| A retry waits through the ledger of the identity. | `test_a_lost_get_waits_through_the_identity_ledger` |

## Feasibility

The premise holds at `origin/main` (commit d254410c). Each check below was made on the code of that commit, or on the locked library source of the project's virtual environment.

- Line 101 of `src/devops_cli/github/session_transport.py` defines `_UNREAD` with `httpx2.HTTPError`. Line 344 catches `(HTTPException, *_UNREAD)` and raises `classify_http_error` with no retry. Line 269 is `handle_rate_limit_error`. It takes an `HTTPException` only.
- gidgethub 6.0.0 calls `self._request` at `gidgethub/abc.py` line 229, in a `try` block with a `finally` and no `except`. Its `except HTTPException` handler at line 245 calls the rate-limit hook. A transport error never reaches the hook.
- In `httpx2/_exceptions.py`, `RemoteProtocolError` (line 243), `ReadError` (line 186) and `WriteError` (line 192) subclass `TransportError`. They are transport errors, not HTTP answers.
- In `httpcore2/_sync/http2.py`, lines 313 and 314 raise `RemoteProtocolError` for an h2 `StreamReset`. Line 328 raises it for a `ConnectionTerminated`. So the h2 failures named in the issue reach the transport as `RemoteProtocolError`.
- The text of the CI failure matches `classify_http_error` for a non-HTTP error: `GitHub gave no readable answer to {request}: {type(error).__name__}`. The fail-to-pass run on `origin/main` printed the same text for `RemoteProtocolError`.
- The open pull request list (`uv run devops pr list --limit 100`, 2026-11-05) has no row for issue 3497. The list shows no changed files, so the overlap check uses the local branch below.
- A local branch, `fix/3497-cut-unchanged-github-reads`, edits `session_transport.py` and `rate_limiter.py`. It has eight commits past `origin/main` and is not on `origin`. See the design for the overlap.

The Service rounds in the issue print `StreamReset` and `ConnectionTerminated`. Origin/main prints only the class name, `RemoteProtocolError`. The image that printed those names is not on main. A person must confirm this. It does not change the premise.

## Existing Tool Considered

- gidgethub 6.0.0 covers an HTTP answer only. Its hook `handle_rate_limit_error` runs for an `HTTPException` (`gidgethub/abc.py` line 245). A transport error does not reach it. The change rejects this tool.
- httpx2 2.13.1 has a transport option `retries`. Its docstring names connection retries (`httpx2/_transports/default.py` line 18). It does not resend a GET whose connection ended after the request went out. It does not pace on the identity's ledger. The change rejects this option.
- tenacity is already a dependency (`src/devops_cli/github/rate_limiter.py` line 38). Its `Retrying` could drive the loop, with a `sleep` that waits on the ledger. Each attempt still needs the pacing step and the charge step in a worker thread. So the wrapper would hold the same code, and the gain is small. The change rejects tenacity for the project loop.
- Build instead. The source change adds 99 lines and removes 14. The tests add 73 lines and five tests. The change adds one spec capability and no dependency, so no library needs keeping or fixing. Tokens are not measured. Elapsed time is one working session.

The change deletes no internal code.
