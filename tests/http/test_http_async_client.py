"""Tests for async HTTP/2 client creation and connection pool configuration."""

from __future__ import annotations

import pytest

from devops_cli.http.client import new_async_http_client
from devops_cli.http.egress import EgressLevel
from tests.support.fakes.github import GitHubApiFake


@pytest.mark.asyncio
async def test_async_http_client() -> None:
    """Verify creation and configuration of async HTTP client."""
    client = new_async_http_client(level=EgressLevel.PUBLIC, read_timeout=5.0)
    assert client.timeout.read == 5.0
    await client.aclose()


def test_the_fake_github_api_and_stub_web_refuse_to_share_a_test(
    github_api: GitHubApiFake, request: pytest.FixtureRequest
) -> None:
    """Both fake `httpx2.AsyncClient`, so a test asking for both fails instead of one winning."""
    with pytest.raises(RuntimeError, match=r"both fake httpx2\.AsyncClient"):
        request.getfixturevalue("stub_web")
