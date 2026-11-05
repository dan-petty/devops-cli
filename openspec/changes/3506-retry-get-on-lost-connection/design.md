# Design

## Decisions

- **Retry inside `SessionGitHubAPI._request`, within gidgethub's own attempt.** gidgethub calls the rate-limit hook only in its `except HTTPException` handler (`gidgethub/abc.py` line 245). Its `await self._request` (line 229) has no handler for a transport error. So the retry sits in the session's `_request`. There, each attempt is paced, sent and charged. The loop resends the same URL, so a listing resends only the page that failed.
- **Retry a GET that raises `httpx2.RemoteProtocolError`, `httpx2.ReadError` or `httpx2.WriteError`.** Each is a transport error (`httpx2/_exceptions.py` lines 186, 192 and 243). Each means the connection ended or failed. GitHub may have sent no complete answer. A GET does not change state on GitHub, so a resend is safe. The h2 failures in the issue (`StreamReset`, `ConnectionTerminated`) reach the session as `RemoteProtocolError` (`httpcore2/_sync/http2.py` lines 313, 314 and 328).
- **Do not retry a write.** GitHub may have applied a write whose connection was lost. The session sends a POST, PATCH, PUT or DELETE once.
- **Do not retry the other transport errors.** `httpx2.ConnectError` and `httpx2.ConnectTimeout` are not retried, as the issue requires and as the module docstring states. A refused connect puts no request on the wire. The factory's connect bound decides a slow connect. `httpx2.ReadTimeout` is not retried, because a slow answer is not a lost connection. The factory's read bound decides it. `httpx2.ProxyError` and `httpx2.LocalProtocolError` are not retried, because a resend gives the same result.
- **Keep `WriteError` on a GET.** The plan left this as an open question. The session keeps it, because GitHub received no complete request. The owner may drop it to match the narrower wording of the issue. That change is one line in the tuple `_LOST_CONNECTION`.
- **Accept a budget of up to nine sends.** A GET has three gidgethub attempts (`DEFAULT_GH_MAX_RETRIES` plus one). Each attempt has up to `DEFAULT_GH_MAX_RETRIES` resends for a lost connection. So one GET sends at most nine requests. The module docstring and ADR 0006 state this bound. A shared budget would need state across gidgethub's attempts. gidgethub does not pass that state to `_request`.
- **Wait from the read floor, on the ledger.** Each resend paces through `self._pace`, which waits its turn on the ledger of the identity. The resend then waits the delay that `retry_delay(None, attempt=..., floor=DEFAULT_GH_SERVER_ERROR_RETRY_FLOOR_SECONDS)` gives. It records that wait with `record_throttle` and sleeps through `self.sleep`. This is the path a read 5xx takes. So the ledger and the metrics see one kind of wait.
- **Name the exception class in the refusal.** `refused_retry` accepts `HTTPException | httpx2.TransportError`. For a transport error, it names the class and carries no status. A refused wait then reads `(GET <path>, RemoteProtocolError)`.

## Rejected alternatives

- **gidgethub's `handle_rate_limit_error` hook.** It runs only for `HTTPException` (`gidgethub/abc.py` line 245). A transport error never reaches it. The change rejects the hook.
- **httpx2 transport option `retries`.** Its docstring names connection retries (`httpx2/_transports/default.py` line 18). It does not resend a request whose connection ended after the request went out. It does not pace on the identity's ledger. The change rejects the option.
- **tenacity around `_request`.** tenacity is already a dependency (`src/devops_cli/github/rate_limiter.py` line 38). Its `Retrying` could drive the loop, with `sleep` set to the ledger's wait. Each attempt still needs the pacing step and the charge step in a worker thread, so the wrapper would hold the same code. The gain is small. The change rejects it for the project loop.
- **Retry a connect failure too.** The issue names a refused connect as unretried, and the module docstring says so. A retry would change that rule without a stated reason. The change rejects it.

## Cost of the build

The source change adds 99 lines and removes 14, in `session_transport.py` and `error_classifier.py`. The tests add 73 lines and five tests. The change adds one spec capability and one ADR paragraph. It adds no dependency, so nothing in a library needs keeping or fixing. Tokens are not measured. Elapsed time is one working session.

## Overlap with issue 3497

A local branch, `fix/3497-cut-unchanged-github-reads`, has eight commits past `origin/main`. It is not on `origin`. It edits `session_transport.py` and `rate_limiter.py`. Its hunks touch `SessionGitHubAPI`, which this change also edits. This branch does not contain those commits. When issue 3497 merges, its changes may conflict with the loop here. A person or the next agent resolves that conflict at merge time.

## Open items for a person

- The Service rounds in the issue print `StreamReset` and `ConnectionTerminated`. Origin/main prints `RemoteProtocolError` for both. The image that printed the h2 names is not on main. A person must confirm which image ran those rounds.
