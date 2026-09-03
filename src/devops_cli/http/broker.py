"""Unified Async HTTP/2 Connection Broker with SSRF Isolation & Telemetry."""

from __future__ import annotations

import os
import threading
from typing import Any

try:
    import httpx2 as httpx
except ImportError:
    import httpx  # type: ignore[no-redef]

from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.http.validation import validate_service_url
from devops_cli.telemetry.context import inject_traceparent_headers


class HttpClientBroker:
    """Thread-safe connection pool broker managing persistent HTTP/2 clients."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        allow_private_networks: bool | None = None,
        enable_http2: bool = True,
    ) -> None:
        self.timeout = timeout
        self.allow_private_networks = (
            allow_private_networks
            if allow_private_networks is not None
            else os.environ.get("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "").lower() in ("true", "1")
        )
        self.enable_http2 = enable_http2
        self._lock = threading.Lock()
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    def validate_url(self, url: str) -> str:
        """Validate destination URL against SSRF and private network policies."""
        validate_service_url(url, allow=self.allow_private_networks)
        return url

    def build_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Construct request headers with OpenTelemetry traceparent context propagation."""
        base_headers = dict(headers or {})
        base_headers.setdefault("User-Agent", "devops-cli/0.2.9")
        return inject_traceparent_headers(base_headers)

    def _validate_request(self, request: httpx.Request) -> None:
        """Validate request and redirect URLs against SSRF policies."""
        validate_service_url(str(request.url), purpose="http", allow=self.allow_private_networks)

    def get_client(self) -> httpx.Client:
        """Return thread-safe shared synchronous HTTP client."""
        with self._lock:
            if self._sync_client is None or self._sync_client.is_closed:
                self._sync_client = httpx.Client(
                    timeout=self.timeout,
                    http2=self.enable_http2,
                    follow_redirects=True,
                    event_hooks={"request": [self._validate_request]},
                )
            return self._sync_client

    async def get_async_client(self) -> httpx.AsyncClient:
        """Return shared asynchronous HTTP client."""
        with self._lock:
            if self._async_client is None or self._async_client.is_closed:
                self._async_client = httpx.AsyncClient(
                    timeout=self.timeout,
                    http2=self.enable_http2,
                    follow_redirects=True,
                    event_hooks={"request": [self._validate_request]},
                )
            return self._async_client

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        allow_private_network: bool | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform a synchronous HTTP request via the managed connection pool."""
        client = self.get_client()
        call_headers = self.build_headers(headers)
        return client.request(
            method, url, headers=call_headers, timeout=timeout or self.timeout, **kwargs
        )

    def close(self) -> None:
        """Close synchronous client connections."""
        with self._lock:
            if self._sync_client is not None and not self._sync_client.is_closed:
                self._sync_client.close()
                self._sync_client = None

    async def aclose(self) -> None:
        """Close asynchronous client connections."""
        with self._lock:
            if self._async_client is not None and not self._async_client.is_closed:
                await self._async_client.aclose()
                self._async_client = None

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
