"""Tests for async HTTP/2 client creation and connection pool configuration."""

from __future__ import annotations

import pytest

from devops_cli.http.client import new_async_http_client


@pytest.mark.asyncio
async def test_async_http_client() -> None:
    """Verify creation and configuration of async HTTP client."""
    client = new_async_http_client(read_timeout=5.0)
    assert client.timeout.read == 5.0
    await client.aclose()
