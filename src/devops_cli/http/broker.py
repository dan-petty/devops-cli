"""Unified Async HTTP/2 Connection Broker with SSRF Isolation & Telemetry."""

from __future__ import annotations

import threading
from typing import Any

try:
    import httpx2 as httpx
except ImportError:
    import httpx  # type: ignore[no-redef]

from devops_cli.config.constants import CONST_HTTP_EGRESS_POLICY_EXTENSION
from devops_cli.config.defaults import DEFAULT_HTTP_MAX_REDIRECTS, DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.exceptions import InvalidURLError
from devops_cli.http.client import new_async_http_client, new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.telemetry.context import inject_traceparent_headers


class HttpClientBroker:
    """Thread-safe broker keeping one persistent HTTP/2 client per egress level.

    Each client dials only the addresses its level allows, checked at the connect for every
    redirect hop (`devops_cli.http.egress`). A connection one level opened is never reused by
    another, because each level has a client, and so a connection pool, of its own.
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        enable_http2: bool = True,
    ) -> None:
        self.timeout = timeout
        self.enable_http2 = enable_http2
        self._lock = threading.Lock()
        self._sync_clients: dict[EgressLevel, httpx.Client] = {}
        self._async_clients: dict[EgressLevel, httpx.AsyncClient] = {}

    def build_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Construct request headers with OpenTelemetry traceparent context propagation."""
        base_headers = dict(headers or {})
        base_headers.setdefault("User-Agent", "devops-cli/0.2.9")
        return inject_traceparent_headers(base_headers)

    @staticmethod
    def _validate_request(request: httpx.Request) -> None:
        """Veto the request and each redirect hop before it is sent.

        A request carrying its own egress policy is held to that policy, and every hop must be
        http or https. Which addresses a hop may reach is the connect's decision, made for the
        address dialled, so the hook does no lookup.
        """
        if policy := request.extensions.get(CONST_HTTP_EGRESS_POLICY_EXTENSION):
            policy(str(request.url))
        if request.url.scheme not in ("http", "https"):
            raise InvalidURLError(
                str(request.url)[:256], reason="Only http and https URLs may be requested"
            )

    def new_client(self, level: EgressLevel) -> httpx.Client:
        """Return a synchronous client of its own at `level`, which the caller closes.

        It follows the broker's redirect limit and vetoes each hop as the shared clients do, but
        shares no connection pool or cookie jar with them.
        """
        return new_http_client(
            level=level,
            timeout=self.timeout,
            http2=self.enable_http2,
            follow_redirects=True,
            max_redirects=DEFAULT_HTTP_MAX_REDIRECTS,
            event_hooks={"request": [self._validate_request]},
        )

    def get_client(self, level: EgressLevel) -> httpx.Client:
        """Return the thread-safe shared synchronous client for `level`."""
        with self._lock:
            client = self._sync_clients.get(level)
            if client is None or client.is_closed:
                client = self._sync_clients[level] = self.new_client(level)
            return client

    async def _async_validate_request(self, request: httpx.Request) -> None:
        """Veto each async request and redirect hop; like the sync hook, it does no lookup."""
        self._validate_request(request)

    async def get_async_client(self, level: EgressLevel) -> httpx.AsyncClient:
        """Return the shared asynchronous client for `level`."""
        with self._lock:
            client = self._async_clients.get(level)
            if client is None or client.is_closed:
                client = self._async_clients[level] = new_async_http_client(
                    level=level,
                    timeout=self.timeout,
                    http2=self.enable_http2,
                    follow_redirects=True,
                    max_redirects=DEFAULT_HTTP_MAX_REDIRECTS,
                    event_hooks={"request": [self._async_validate_request]},
                )
            return client

    def request(
        self,
        method: str,
        url: str,
        *,
        level: EgressLevel,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform a synchronous HTTP request through the shared client for `level`."""
        client = self.get_client(level)
        req = client.build_request(
            method,
            url,
            headers=self.build_headers(headers),
            timeout=timeout or self.timeout,
            **kwargs,
        )
        return client.send(req)

    async def arequest(
        self,
        method: str,
        url: str,
        *,
        level: EgressLevel,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform an asynchronous HTTP request through the shared client for `level`."""
        client = await self.get_async_client(level)
        req = client.build_request(
            method,
            url,
            headers=self.build_headers(headers),
            timeout=timeout or self.timeout,
            **kwargs,
        )
        return await client.send(req)

    def close(self) -> None:
        """Close the synchronous clients' connections."""
        with self._lock:
            clients = list(self._sync_clients.values())
            self._sync_clients.clear()
        for client in clients:
            if not client.is_closed:
                client.close()

    async def aclose(self) -> None:
        """Close the asynchronous clients' connections."""
        with self._lock:
            clients = list(self._async_clients.values())
            self._async_clients.clear()
        for client in clients:
            if not client.is_closed:
                await client.aclose()

    def __enter__(self) -> HttpClientBroker:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    async def __aenter__(self) -> HttpClientBroker:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()


# Module-level default broker instance
DEFAULT_HTTP_BROKER = HttpClientBroker()


def get_broker() -> HttpClientBroker:
    """Return the global shared HttpClientBroker instance."""
    return DEFAULT_HTTP_BROKER
