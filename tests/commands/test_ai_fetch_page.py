"""`devops ai fetch-page` reads the text of one page through the Crawl4AI service (#3892).

The service is the HTTP fake and its token is in the keyring fake. The client has its own tests in
`tests/ai/test_page_text.py`: these tests cover what the command prints and how it exits.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.defaults import DEFAULT_PAGE_TEXT_MAX_CHARS
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring

_SERVICE = "http://127.0.0.1:11235"
_MD_URL = f"{_SERVICE}/md"
_TOKEN = "c4a-secret-token"
_PAGE = "https://example.com/docs/page"
_REPLY = {"url": _PAGE, "markdown": "# Page title\n\nThe body of the page.", "success": True}


@pytest.fixture
def service(config: Callable[..., Path], keyring_store: FakeKeyring, web: WebFake) -> WebFake:
    """The Crawl4AI service behind a port-forward, with its token in the credential store."""
    config(crawl4ai={"url": _SERVICE})
    keyring_store.set_password("devops-cli", "crawl4ai_api_token", _TOKEN)
    return web


def test_the_output_holds_the_source_line_and_the_page_text(
    cli: Callable[..., Any], service: WebFake
) -> None:
    service.respond("POST", _MD_URL, 200, _REPLY)

    result = cli("ai", "fetch-page", _PAGE)

    assert result.exit_code == 0
    assert f"Source: {_PAGE}" in result.output
    assert "# Page title\n\nThe body of the page." in result.output
    assert result.output.index("Source:") < result.output.index("# Page title")
    assert "truncated" not in result.output
    assert _TOKEN not in result.output


def test_a_cut_text_says_so(cli: Callable[..., Any], service: WebFake) -> None:
    reply = {**_REPLY, "markdown": "x" * (DEFAULT_PAGE_TEXT_MAX_CHARS + 10)}
    service.respond("POST", _MD_URL, 200, reply)

    result = cli("ai", "fetch-page", _PAGE)

    assert (result.exit_code, "truncated" in result.output) == (0, True)


@pytest.mark.parametrize(
    ("page", "reason"),
    [
        ("file:///etc/passwd", "Only http and https"),
        ("http://192.0.2.5/admin", "public web host"),
    ],
)
def test_a_refused_page_url_exits_non_zero_with_the_reason_and_sends_nothing(
    cli: Callable[..., Any], service: WebFake, page: str, reason: str
) -> None:
    result = cli("ai", "fetch-page", page)

    assert result.exit_code != 0
    assert reason in result.output
    assert service.recorded == []


def test_an_empty_service_setting_is_named(
    cli: Callable[..., Any], config: Callable[..., Path], web: WebFake
) -> None:
    config()

    result = cli("ai", "fetch-page", _PAGE)

    assert result.exit_code != 0
    assert "crawl4ai.url" in result.output
    assert web.recorded == []


def test_a_failed_fetch_exits_non_zero_with_the_status(
    cli: Callable[..., Any], service: WebFake
) -> None:
    service.respond("POST", _MD_URL, 503, {"detail": "busy"})

    result = cli("ai", "fetch-page", _PAGE)

    assert result.exit_code != 0
    assert "HTTP 503" in result.output
    assert _TOKEN not in result.output


def test_a_dry_run_sends_no_request_and_shows_the_request(
    cli: Callable[..., Any], service: WebFake
) -> None:
    result = cli("ai", "fetch-page", _PAGE, "--dry-run")

    assert result.exit_code == 0
    assert service.recorded == []
    assert f"POST {_MD_URL}" in result.output
    assert _PAGE in result.output
    assert "<crawl4ai.api_token>" in result.output
    assert _TOKEN not in result.output


def test_a_dry_run_still_refuses_a_page_url_and_an_empty_setting(
    cli: Callable[..., Any], config: Callable[..., Path], web: WebFake
) -> None:
    config()

    unset = cli("ai", "fetch-page", _PAGE, "--dry-run")
    refused = cli("ai", "fetch-page", "http://192.0.2.5/", "--dry-run")

    assert (unset.exit_code != 0, "crawl4ai.url" in unset.output) == (True, True)
    assert refused.exit_code != 0
    assert web.recorded == []
