"""The retry policy of the reads of a cluster service, and the one error that ends them (#5532).

A cluster service, such as Prometheus after a node drain, can answer 503 for some seconds while its
pod starts. `http_client(level, retries=SERVICE_READ_RETRY)` puts `ReadRetryTransport` on the
transport of the client. It sends a GET, HEAD or OPTIONS request again after 429, 502, 503 or 504,
and after a failed connect or read. The waits back off exponentially with jitter, obey
`Retry-After`, and stop at a small number of attempts and at a time bound. The transport sends a
request with another method one time, gives a reply with another status at once, and raises an
egress refusal (`SSRFBlockedError`, which is not an httpx2 error) at once.

The transport is transparent: when the attempts or the time end, it gives the last reply, or raises
the last network error, as one attempt does. So each client keeps its own check of a status, and it
can read the body of a reply. The transport writes the attempts and their time on the request, and
`service_error` reads them to make the one `ServiceRequestError` line of a failed request.

The loop is `tenacity.Retrying`. The pydantic-ai transport behind the integer form of `retries`
imports `pydantic_ai`, 0.55 s and 850 modules, and closes the reply of a failed status.
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Final, cast

import httpx2
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential_jitter,
)
from tenacity.stop import stop_base

from devops_cli.config.constants import CONST_MAX_ERROR_DETAIL_LENGTH
from devops_cli.core import clock
from devops_cli.exceptions.http import ServiceRequestError
from devops_cli.lang import ERRORS

if TYPE_CHECKING:
    from concurrent.futures import Future

# RFC 9110 section 9.2.2: the methods whose repeat has the effect of one request. The clients of
# this policy read with GET.
_IDEMPOTENT_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})

# A service that limits the rate, or a gateway or proxy whose backend is not ready. A 500 is an
# internal error of the service, which a second attempt does not repair.
_RETRY_STATUSES: Final = frozenset(
    {
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    }
)

# A connect or a read that failed. `RemoteProtocolError` is the server that closed the connection
# before its reply, as a pod that stops does.
_RETRY_ERRORS: Final = (
    httpx2.ConnectError,
    httpx2.ConnectTimeout,
    httpx2.ReadError,
    httpx2.ReadTimeout,
    httpx2.RemoteProtocolError,
)

_ATTEMPTS_EXTENSION: Final = "devops_cli.attempts"
_JSON_MEDIA_TYPE: Final = "application/json"
_TEXT_MEDIA_TYPE: Final = "text/plain"


@dataclass(frozen=True, slots=True)
class ReadRetryPolicy:
    """How a client sends a read again: the attempts, the waits and the time bound.

    The wait before attempt n + 1 is `first_wait_seconds * 2 ** (n - 1)` plus a jitter of up to
    `jitter_seconds`, at most `max_wait_seconds` with the jitter, and at least the delay of a
    `Retry-After` header. No attempt starts when the time since the first attempt plus the next
    wait is `budget_seconds` or more.
    """

    attempts: int = 4
    first_wait_seconds: float = 1.0
    max_wait_seconds: float = 8.0
    jitter_seconds: float = 1.0
    budget_seconds: float = 20.0


# The policy of the reads of a cluster service. Its waits are 7 s to 10 s in total, and its time
# bound is less than the shortest command timeout (the MCP fast timeout, 30 s).
SERVICE_READ_RETRY: Final = ReadRetryPolicy()


@dataclass(frozen=True, slots=True)
class RequestAttempts:
    """The attempts of one request and the seconds from the first attempt to the last reply."""

    count: int
    seconds: float


class ReadRetryTransport(httpx2.BaseTransport):
    """Send an idempotent request again after a transient failure, as `policy` says."""

    def __init__(self, wrapped: httpx2.BaseTransport, policy: ReadRetryPolicy) -> None:
        self._wrapped = wrapped
        self._policy = policy
        self._backoff = wait_exponential_jitter(
            initial=policy.first_wait_seconds,
            max=policy.max_wait_seconds,
            jitter=policy.jitter_seconds,
        )

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        started = clock.monotonic()
        count = 0

        def attempt() -> httpx2.Response:
            nonlocal count
            count += 1
            return self._wrapped.handle_request(request)

        try:
            if request.method not in _IDEMPOTENT_METHODS:
                return attempt()
            return self._retrying(started)(attempt)
        finally:
            request.extensions[_ATTEMPTS_EXTENSION] = RequestAttempts(
                count, clock.monotonic() - started
            )

    def close(self) -> None:
        self._wrapped.close()

    def _retrying(self, started: float) -> Retrying:
        """The loop of one request that started at `started` on the clock seam."""
        return Retrying(
            stop=stop_after_attempt(self._policy.attempts)
            | _StopPastBudget(started, self._policy.budget_seconds),
            wait=self._wait,
            retry=retry_if_exception_type(_RETRY_ERRORS) | retry_if_result(_is_transient_reply),
            before_sleep=_close_reply,
            retry_error_callback=_last_outcome,
            sleep=clock.sleep,
        )

    def _wait(self, state: RetryCallState) -> float:
        """The jittered backoff, or the delay of a `Retry-After` header when it is longer."""
        backoff = float(self._backoff(state))
        asked = _retry_after(state)
        return backoff if asked is None else max(backoff, asked)


class _StopPastBudget(stop_base):
    """Stop when the time since `started` plus the next wait is `budget` seconds or more.

    Tenacity's own `stop_before_delay` reads `time.monotonic`, which the clock seam does not
    reach. The waits go through the seam too, so a test moves both.
    """

    def __init__(self, started: float, budget: float) -> None:
        self._started = started
        self._budget = budget

    def __call__(self, retry_state: RetryCallState) -> bool:
        elapsed = clock.monotonic() - self._started
        return elapsed + retry_state.upcoming_sleep >= self._budget


def _is_transient_reply(response: httpx2.Response) -> bool:
    return response.status_code in _RETRY_STATUSES


def _close_reply(state: RetryCallState) -> None:
    """Close the reply that the loop sends again, so its connection goes back to the pool."""
    if state.outcome is not None and not state.outcome.failed:
        state.outcome.result().close()


def _last_outcome(state: RetryCallState) -> httpx2.Response:
    """The last reply when the loop ends, or the last error raised again, as one attempt gives.

    Tenacity calls it only after an attempt, so the state holds an outcome.
    """
    return cast("Future[httpx2.Response]", state.outcome).result()


def _retry_after(state: RetryCallState) -> float | None:
    """The delay in seconds of the `Retry-After` header of the last reply, if it has one."""
    if state.outcome is None or state.outcome.failed:
        return None
    header = state.outcome.result().headers.get("retry-after")
    if header is None:
        return None
    from devops_cli.github.error_classifier import parse_retry_after

    return parse_retry_after(header)


def request_attempts(error: httpx2.HTTPError) -> RequestAttempts:
    """The attempts that `ReadRetryTransport` recorded on the request of `error`; one attempt with
    no time for a request that went through no policy."""
    try:
        request = error.request
    except RuntimeError:
        return RequestAttempts(1, 0.0)
    recorded = request.extensions.get(_ATTEMPTS_EXTENSION)
    return recorded if isinstance(recorded, RequestAttempts) else RequestAttempts(1, 0.0)


def service_error(
    service: str, error: httpx2.HTTPError, *, setting: str | None = None
) -> ServiceRequestError:
    """The one error line of a failed request to `service`, from the last httpx2 error.

    The line names the service, the HTTP status with the error text of the reply or the network
    error, the attempts, the time and a hint. `setting` names the setting of the address of the
    service, for the hint of a network error.
    """
    attempts = request_attempts(error)
    texts = ERRORS.http
    status: int | None = None
    if isinstance(error, httpx2.HTTPStatusError):
        status = error.response.status_code
        problem = _status_problem(error.response)
    else:
        problem = texts.network.format(
            error_type=type(error).__name__, error=_one_line(str(error)) or type(error).__name__
        )
    count = (
        texts.one_attempt if attempts.count == 1 else texts.attempts.format(count=attempts.count)
    )
    message = texts.service_failed.format(
        service=service,
        attempts=count,
        seconds=attempts.seconds,
        problem=problem,
        hint=_hint(status, setting),
    )
    return ServiceRequestError(
        message,
        service=service,
        status_code=status,
        attempts=attempts.count,
        seconds=attempts.seconds,
    )


def _status_problem(response: httpx2.Response) -> str:
    texts = ERRORS.http
    detail = _reply_detail(response)
    if detail is None:
        return texts.status.format(status=response.status_code, reason=response.reason_phrase)
    return texts.status_detail.format(
        status=response.status_code, reason=response.reason_phrase, detail=detail
    )


def _reply_detail(response: httpx2.Response) -> str | None:
    """The error text of a reply: the `error` field (after its `errorType`) or the `message` field
    of a JSON body, as Prometheus and Grafana give them, or the first line of a plain text body, as
    Loki gives it."""
    media_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
    text: str | None = None
    if media_type == _JSON_MEDIA_TYPE:
        text = _json_error(response)
    elif media_type == _TEXT_MEDIA_TYPE:
        text = next(iter(response.text.strip().splitlines()), None)
    text = _one_line(text or "")
    return text[:CONST_MAX_ERROR_DETAIL_LENGTH] if text else None


def _one_line(text: str) -> str:
    """`text` as one line with no full stop at its end, because the error line adds its own."""
    return " ".join(text.split()).rstrip(".")


def _json_error(response: httpx2.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    match body:
        case {"error": str(error), "errorType": str(kind)} if kind:
            return f"{kind}: {error}"
        case {"error": str(error)}:
            return error
        case {"message": str(message)}:
            return message
        case _:
            return None


def _hint(status: int | None, setting: str | None) -> str:
    texts = ERRORS.http
    match status:
        case None if setting:
            return texts.hint_no_answer.format(setting=setting)
        case None:
            return texts.hint_no_answer_address
        case HTTPStatus.TOO_MANY_REQUESTS:
            return texts.hint_rate_limited
        case code if code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            return texts.hint_not_ready
        case _:
            return texts.hint_refused


__all__ = [
    "SERVICE_READ_RETRY",
    "ReadRetryPolicy",
    "ReadRetryTransport",
    "RequestAttempts",
    "request_attempts",
    "service_error",
]
