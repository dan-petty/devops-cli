"""Tests for async HTTP/2 client creation and connection pool configuration."""

from __future__ import annotations

import pytest

from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import async_http_client


@pytest.mark.asyncio
async def test_async_http_client() -> None:
    """Verify creation and configuration of async HTTP client."""
    client = async_http_client(EgressLevel.PUBLIC, read_timeout=5.0)
    assert client.timeout.read == 5.0
    await client.aclose()
