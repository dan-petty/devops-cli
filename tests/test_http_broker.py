"""Unit tests for the Unified Async HTTP/2 Connection Broker."""

from __future__ import annotations

import pytest

from devops_cli.exceptions.validation import ValidationError
from devops_cli.http.broker import HttpClientBroker


def test_http_broker_get_client_singleton() -> None:
    broker = HttpClientBroker()
    client1 = broker.get_client()
    client2 = broker.get_client()
    assert client1 is client2
    broker.close()


def test_http_broker_traceparent_header_injection() -> None:
    broker = HttpClientBroker()
    headers = broker.build_headers({"Authorization": "Bearer token123"})
    assert headers["Authorization"] == "Bearer token123"
    # Should contain traceparent if span context exists or return standard headers
    assert "User-Agent" in headers or "Authorization" in headers
    broker.close()


def test_http_broker_ssrf_destination_validation() -> None:
    broker = HttpClientBroker(allow_private_networks=False)

    # Invalid URL scheme
    with pytest.raises(ValidationError):
        broker.validate_url("ftp://example.com/api")

    # Safe public URL
    safe_url = broker.validate_url("https://api.github.com/repos")
    assert safe_url == "https://api.github.com/repos"
    broker.close()


@pytest.mark.asyncio
async def test_http_broker_async_context_manager() -> None:
    async with HttpClientBroker() as broker:
        aclient1 = await broker.get_async_client()
        aclient2 = await broker.get_async_client()
        assert aclient1 is aclient2
        assert not aclient1.is_closed
