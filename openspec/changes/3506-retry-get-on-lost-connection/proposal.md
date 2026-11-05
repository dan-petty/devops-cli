# Proposal

## Why

Issue #3506 asks for a retry of a GitHub read whose connection is lost. A GET that loses its connection fails at once, with no retry. One lost connection then turns a CI job red, and it counts as a failed round of a Service row, which suspends the row sooner. The CI run after 2026-11-04T15:05Z printed `GitHub gave no readable answer to GET /repos/dan-petty/devops-cli/actions/runs/41772844168/jobs?per_page=100: RemoteProtocolError`.

## What Changes

- `src/devops_cli/github/session_transport.py`: `SessionGitHubAPI._request` sends a GET again when its connection is lost. The lost connections are `httpx2.RemoteProtocolError`, `httpx2.ReadError` and `httpx2.WriteError`. The session sends the GET at most `DEFAULT_GH_MAX_RETRIES` more times.
- Each resend paces on the ledger of the session's identity. It waits from `DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS`, and the wait is recorded as a throttle, as a read 5xx is.
- A write that loses its connection is never sent again, because GitHub may have applied it.
- A refused connect, a connect timeout, a read timeout, a proxy error and a local protocol error are not retried. The module docstring states this rule.
- `src/devops_cli/github/error_classifier.py`: `refused_retry` accepts a transport error, which has no HTTP status.
- `docs/adr/0006-github-session-requests-go-through-gidgethub.md`: the Retries paragraph states the rule.
- The change adds the spec capability `github-session-retry`. A consumer observes it: a `devops` command that reads GitHub sends the read again, and a command that fails names the request. So the change carries a spec delta.
- The change fits one pull request. It closes #3506 only.
- The change deletes no internal code.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| A `RemoteProtocolError` on the first GET and an answer on the second gives the normal result. | `test_a_get_that_loses_its_connection_is_sent_again` |
| A `RemoteProtocolError` on each attempt ends after `DEFAULT_GH_MAX_RETRIES` retries, and the error stays `GitHubUnreadError` with its present text. | `test_a_get_that_loses_its_connection_on_every_attempt_raises_after_the_retries` |
| A POST that loses its connection sends one request. | `test_a_write_that_loses_its_connection_is_sent_once` |
| A listing that loses its connection on page 3 sends page 3 again and not page 1, and it returns each item once. | `test_a_listing_that_loses_page_3_sends_page_3_again` |
| `httpx2.ConnectError` on a GET sends one request. | `test_no_readable_answer_raises_the_unread_error_without_a_retry[connect-error]`, kept as the regression test |
| A retry waits through the ledger of the identity. | `test_a_lost_get_waits_through_the_identity_ledger` |

## Feasibility

The premise holds at `origin/main` (commit d254410c). Each check below was made on the code of that commit, or on the locked library source of the project's virtual environment.

- `src/devops_cli/github/session_transport.py` line 101 defines `_UNREAD` with `httpx2.HTTPError`. Line 344 catches `(HTTPException, *_UNREAD)` and raises `classify_http_error` with no retry. Line 269 is `handle_rate_limit_error`, which takes an `HTTPException` only.
- gidgethub 6.0.0, `gidgethub/abc.py` line 229, calls `self._request` in a `try` block with a `finally` and no `except`. Its `except HTTPException` handler at line 245 calls the rate-limit hook. So a transport error never reaches the hook.
- httpx2 2.13.1, `httpx2/_exceptions.py`: `RemoteProtocolError` (line 243), `ReadError` (line 186) and `WriteError` (line 192) all subclass `TransportError`, so they are transport errors and not HTTP answers.
- httpcore2 2.13.1, `httpcore2/_sync/http2.py` lines 313 and 314 raise `RemoteProtocolError` for an h2 `StreamReset`, and line 328 raises it for a `ConnectionTerminated`. So the h2 failures named in the issue are `RemoteProtocolError` at the transport seam.
- The text of the CI failure matches `classify_http_error` for a non-HTTP error: `GitHub gave no readable answer to {request}: {type(error).__name__}` (`src/devops_cli/github/error_classifier.py`). Origin/main prints the same text for `RemoteProtocolError`.
- Open pull requests: `uv run devops pr list --limit 100` on 2026-11-05 lists no pull request for issue 3497 and none that changes `session_transport.py`. A local branch `fix/3497-cut-unchanged-github-reads` edits `session_transport.py`. It is not on `origin`. See the design for the overlap.

The Service rounds in the issue print `StreamReset` and `ConnectionTerminated`. Origin/main prints only the class name, `RemoteProtocolError`. So the image that printed those names is not on main. This is an open item for a person, and it does not change the premise.

## Existing Tool Considered

- gidgethub 6.0.0 covers an HTTP answer only. Its hook `handle_rate_limit_error` runs for an `HTTPException` (`gidgethub/abc.py` line 245), and a transport error does not reach it. Rejected.
- httpx2 2.13.1 has a transport option `retries`. Its docstring names connection retries (`httpx2/_transports/default.py` line 19). It does not resend a GET whose connection ended after the request was sent, and it does not pace on the identity's ledger. Rejected.
- tenacity is already a dependency (`src/devops_cli/github/rate_limiter.py` line 38). Its `retry` decorator could drive the loop, with a `sleep` that waits on the ledger. The loop still calls the pacing step and the charge step on each attempt, in a worker thread, and the ledger wait is project code. The gain is small, so the change keeps a small loop. Rejected.
- Build instead: the change adds about 60 changed lines in two source files, about six tests, and a spec capability. It adds no dependency, so there is no library to keep or fix. Elapsed time is one working session.

The change deletes no internal code. The cost of the project loop is the cost stated above.
