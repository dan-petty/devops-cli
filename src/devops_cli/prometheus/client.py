"""The Prometheus HTTP API behind one client, and the checks that run before a request.

`PrometheusClient` sends the instant query, the range query, and the reads of rules and targets.
It dials only what its egress level allows: the HTTP entry point checks each address at the
connect (`devops_cli.http.entry`). It reads with the retry policy of a cluster service
(`devops_cli.http.retry`), so a Prometheus that starts again after a node drain gets more attempts,
and a request that still fails raises one `ServiceRequestError`. The commands, the rollout gate and
the health gate of `devops infra apply` share it, so no second copy of the instant query exists. A
command prints and exits; this module raises.

`expression_problem` and `parse_duration` hold the checks that save a round trip: a PromQL
expression that is too long or malformed, and a relative duration such as `30m`.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

import httpx2

from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.http.retry import SERVICE_READ_RETRY, service_error
from devops_cli.lang import ERRORS
from devops_cli.prometheus.promql import validate_promql

MAX_PROMQL_LENGTH = 4096
MAX_DURATION_SECONDS = 31_536_000.0  # 365 days

_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class PrometheusContentTypeError(ValueError):
    """Prometheus answered with a content type that is not JSON."""

    def __init__(self, content_type: str) -> None:
        super().__init__(
            ERRORS.prometheus.unexpected_content_type.format(content_type=content_type)
        )
        self.content_type = content_type


class DurationTooLongError(ValueError):
    """A relative duration is longer than 365 days."""


def expression_problem(expr: str) -> str | None:
    """Return why a PromQL expression must not be sent, or None when it may be.

    An over-long or structurally malformed expression fails here, with the offending character
    named, so the round trip is saved and the server's phrasing of the failure is not relayed.
    """
    if len(expr) > MAX_PROMQL_LENGTH:
        return ERRORS.prometheus.expr_too_long.format(max_len=MAX_PROMQL_LENGTH)
    validation = validate_promql(expr)
    if not validation:
        return ERRORS.prometheus.invalid_promql.format(errors=validation.summary)
    return None


def parse_duration(text: str) -> float:
    """Parse a relative duration such as `30m`, `1h` or `7d` to seconds.

    A plain number is seconds. An empty or unreadable text is 0. A duration over 365 days raises
    `DurationTooLongError`.
    """
    if not text:
        return 0.0
    unit = text[-1].lower()
    if unit in _DURATION_UNITS and text[:-1].isdigit():
        seconds = float(int(text[:-1]) * _DURATION_UNITS[unit])
    else:
        try:
            seconds = float(text)
        except ValueError:
            return 0.0
    if seconds > MAX_DURATION_SECONDS:
        raise DurationTooLongError("Duration exceeds maximum allowed value (365 days).")
    return seconds


class PrometheusClient:
    """A client of one Prometheus server, open for the length of a `with` block."""

    def __init__(
        self,
        base_url: str,
        level: EgressLevel,
        *,
        timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._level = level
        self._timeout = timeout
        self._http: httpx2.Client | None = None

    def __enter__(self) -> Self:
        self._http = http_client(self._level, retries=SERVICE_READ_RETRY)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    def query(self, expr: str, *, at: str | None = None) -> dict[str, Any]:
        """Run an instant query and return the JSON answer."""
        params = {"query": expr}
        if at:
            params["time"] = at
        return self._get_json("/api/v1/query", params)

    def query_range(self, expr: str, *, start: str, end: str, step: str) -> dict[str, Any]:
        """Run a range query between two timestamps and return the JSON answer."""
        return self._get_json(
            "/api/v1/query_range", {"query": expr, "start": start, "end": end, "step": step}
        )

    def rules(self) -> dict[str, Any]:
        """Return the recording and alerting rules. An empty answer is an empty document."""
        return self._get_json("/api/v1/rules", allow_empty=True)

    def targets(self) -> dict[str, Any]:
        """Return the scrape targets."""
        return self._get_json("/api/v1/targets")

    def _get_json(
        self, path: str, params: dict[str, str] | None = None, *, allow_empty: bool = False
    ) -> dict[str, Any]:
        """GET `path`; raise `ServiceRequestError` for a failed request after its attempts, or
        `PrometheusContentTypeError` for an answer that is not JSON."""
        if self._http is None:
            raise RuntimeError("PrometheusClient is used outside its `with` block")
        try:
            response = self._http.get(
                f"{self._base_url}{path}", params=params, timeout=self._timeout
            )
            response.raise_for_status()
        except httpx2.HTTPError as exc:
            raise service_error("Prometheus", exc, setting="prometheus.url") from exc
        if allow_empty and not response.content:
            return {}
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise PrometheusContentTypeError(content_type)
        data = response.json()
        return data if isinstance(data, dict) else {}
