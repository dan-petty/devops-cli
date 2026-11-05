# Design

## Decisions

- **Retry inside `SessionGitHubAPI._request`, within gidgethub's own attempt.** gidgethub calls the rate-limit hook only in its `except HTTPException` handler (`gidgethub/abc.py` line 245). Its `await self._request` (line 229) has no handler for a transport error. So the retry sits in the session's `_request`, where each attempt is paced, sent and charged. The loop resends the same URL, so a listing resends only the page that failed.
- **Retry a GET that raises `httpx2.RemoteProtocolError`, `httpx2.ReadError` or `httpx2.WriteError`.** Each is a transport error (`httpx2/_exceptions.py` lines 186, 192, 243). Each means the connection ended or failed, and GitHub may have sent no complete answer. A GET has no effect on GitHub, so a resend is safe. The h2 failures named in the issue (`StreamReset`, `ConnectionTerminated`) reach the session as `RemoteProtocolError` (`httpcore2/_sync/http2.py` lines 313, 314, 328).
- **Do not retry a write.** GitHub may have applied a write whose connection was lost. The session sends a POST, PATCH, PUT or DELETE once.
- **Do not retry the other transport errors.** `httpx2.ConnectError` and `httpx2.ConnectTimeout` stay unretried, as the issue requires and as the module docstring states. A refused connect has no request on the wire, and the factory's connect bound decides a slow connect. `httpx2.ReadTimeout` stays unretried, because a slow answer is not a lost connection and the factory's read bound decides it. `httpx2.ProxyError` and `httpx2.LocalProtocolError` stay unretried, because a resend gives the same result.
- **Keep `WriteError` on a GET.** The plan named this as an open question. The session keeps it, because GitHub received no complete request. The owner may drop it to match the narrower wording of the issue, and that change is one line in the tuple.
- **Accept a budget of up to nine sends.** A GET has three gidgethub attempts (`DEFAULT_GH_MAX_RETRIES` plus one). Each attempt has its own `DEFAULT_GH_MAX_RETRIES` resends for a lost connection. So one GET can send nine requests. The module docstring states this bound. A shared budget would need state across gidgethub's attempts, which gidgethub does not pass to `_request`.
- **Wait from the read floor, on the ledger.** Each resend re-paces with `identity_rate_limiter(identity).acquire`, waits through `retry_delay(None, attempt=..., floor=DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS)`, records the wait with `record_throttle`, and sleeps through `self.sleep`. This is the same path a read 5xx takes, so the ledger and the metrics see one kind of wait.
- **Name the exception class in the refusal.** `refused_retry` accepts `HTTPException | httpx2.TransportError`. For a transport error it names the class and carries no status. A refused wait then reads `(GET <path>, RemoteProtocolError)`.

## Rejected alternatives

- **gidgethub's `handle_rate_limit_error` hook.** It runs only for `HTTPException` (`gidgethub/abc.py` line 245). A transport error never reaches it. Rejected.
- **httpx2 transport option `retries`.** Its docstring names connection retries (`httpx2/_transports/default.py` line 19). It does not resend a request whose connection ended after the request was sent, and it does not pace on the identity's ledger. Rejected.
- **tenacity around `_request`.** tenacity is already a dependency (`src/devops_cli/github/rate_limiter.py` line 38). Its `retry_if_exception_type` and `sleep=` could drive the loop. Each attempt still needs the pacing step and the charge step in a worker thread, so the wrapper would hold the same code. The gain is small. Rejected for the project loop.
- **Retry a connect failure too.** The issue names a refused connect as unretried, and the module docstring says so. A retry would change that rule without a stated reason. Rejected.

## Cost of the build

The build changes about 60 lines in two source files (`session_transport.py`, `error_classifier.py`), about six tests, one spec capability and one ADR paragraph. It adds no dependency, so there is nothing to keep or fix in a library. Elapsed time is one working session.

## Overlap with issue 3497

A local branch `fix/3497-cut-unchanged-github-reads` has three commits past `origin/main`. It edits `session_transport.py` and it is not on `origin`. This branch starts from `origin/main` and does not carry those commits. When issue 3497 merges, its changes to `_request` may conflict with the loop here. The conflict is in the pacing and charge lines of `_request`, and a person or the next agent resolves it at merge time.

## Open items for a person

- The Service rounds in the issue print `StreamReset` and `ConnectionTerminated`. Origin/main prints `RemoteProtocolError` for both. The image that printed the h2 names is not on main. Confirm which image ran those rounds.
