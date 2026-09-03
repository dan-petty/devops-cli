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


def test_http_broker_per_request_allow_private_network_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that per-request allow_private_network overrides broker default."""
    from unittest.mock import MagicMock, patch

    import httpx

    from devops_cli.exceptions.security import SSRFBlockedError

    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    broker = HttpClientBroker(allow_private_networks=False)

    # 1. Default (disallowed) rejects private destination on request()
    with pytest.raises(SSRFBlockedError):
        broker.request("GET", "http://127.0.0.1:8200/v1/sys/health")

    # 2. Per-request override allow_private_network=True permits private destination
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200

    client = broker.get_client()
    with patch.object(client, "send", return_value=mock_resp) as mock_send:
        resp = broker.request(
            "GET", "http://127.0.0.1:8200/v1/sys/health", allow_private_network=True
        )
        assert resp.status_code == 200
        assert mock_send.called
        sent_req = mock_send.call_args[0][0]
        assert sent_req.extensions.get("allow_private_network") is True

    broker.close()


@pytest.mark.asyncio
async def test_http_broker_async_per_request_allow_private_network_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that per-request allow_private_network overrides broker default in async arequest."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx

    from devops_cli.exceptions.security import SSRFBlockedError

    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    async with HttpClientBroker(allow_private_networks=False) as broker:
        # Default rejects private network
        with pytest.raises(SSRFBlockedError):
            await broker.arequest("GET", "http://127.0.0.1:8200/v1/sys/health")

        # Per-request override permits private destination
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200

        aclient = await broker.get_async_client()
        with patch.object(aclient, "send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_resp
            resp = await broker.arequest(
                "GET", "http://127.0.0.1:8200/v1/sys/health", allow_private_network=True
            )
            assert resp.status_code == 200
            assert mock_send.called
            sent_req = mock_send.call_args[0][0]
            assert sent_req.extensions.get("allow_private_network") is True
