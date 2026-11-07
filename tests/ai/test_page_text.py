"""The page-text client of the Crawl4AI service (#3887).

`POST /md` of the service gives the text of a page. The reply shape is fixed in
`tests/fixtures/crawl4ai/md_response.json`; it is the dict that `get_markdown` returns in
`deploy/docker/server.py` of Crawl4AI v0.9.5, lines 616 to 651.

The page URL comes from a model, so the client refuses it before any request. The guard is
`is_loopback_or_private_host` of `devops_cli.core.validation`, which holds `is_non_public_ip` and
`is_cloud_metadata_name`: the test owns no IP or name list of its own.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
import time_machine

from devops_cli.ai.page_text import PageText, fetch_page_text
from devops_cli.config.defaults import (
    DEFAULT_CRAWL4AI_MAX_REPLY_BYTES,
    DEFAULT_CRAWL4AI_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.ai import PageTextError
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.exceptions.validation import InvalidURLError
from devops_cli.telemetry.instruments import CRAWL4AI_FETCHES_TOTAL
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.otlp import FakeCollector
from tests.support.paths import FIXTURES

_SERVICE = "http://crawl4ai.devops.svc.cluster.local:11235"
_MD_URL = f"{_SERVICE}/md"
_TOKEN = "c4a-secret-token"
_PAGE = "https://example.com/docs/page"
_PAGE_WITH_QUERY = "https://example.com/docs/page?session=private-query-value"
_REPLY = json.loads((FIXTURES / "crawl4ai" / "md_response.json").read_text())
_NOW = datetime(2026, 11, 7, 12, 30, tzinfo=UTC)


@pytest.fixture
def service(config: Callable[..., Path], keyring_store: FakeKeyring, web: WebFake) -> WebFake:
    """The Crawl4AI service as the cluster addresses it, with its token in the credential store,
    and the HTTP fake that answers it."""
    config(crawl4ai={"url": _SERVICE})
    keyring_store.set_password("devops-cli", "crawl4ai_api_token", _TOKEN)
    return web


def _serve(web: WebFake, reply: object, status: int = 200) -> None:
    web.respond("POST", _MD_URL, status, reply)


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.ai.page_text" and record.levelno == logging.WARNING
    ]


@time_machine.travel(_NOW, tick=False)
def test_a_fetch_posts_the_page_with_the_bearer_token_and_returns_the_text(
    service: WebFake,
) -> None:
    _serve(service, _REPLY)

    page = fetch_page_text(_PAGE)

    request = service.recorded[0]
    assert (page, request.method, request.url, request.headers["authorization"], request.json) == (
        PageText(source_url=_PAGE, text=_REPLY["markdown"], fetched_at=_NOW, truncated=False),
        "POST",
        _MD_URL,
        f"Bearer {_TOKEN}",
        {"url": _PAGE, "f": "fit"},
    )
    assert len(service.recorded) == 1


def test_a_fetch_waits_for_the_service_as_long_as_the_default_timeout(service: WebFake) -> None:
    _serve(service, _REPLY)

    fetch_page_text(_PAGE)

    assert service.sent[0].extensions["timeout"]["read"] == DEFAULT_CRAWL4AI_TIMEOUT_SECONDS


def test_the_source_url_is_the_url_that_the_caller_asked_for_not_the_one_the_reply_names(
    service: WebFake,
) -> None:
    _serve(service, {**_REPLY, "url": "https://attacker.example.com/"})

    assert fetch_page_text(_PAGE).source_url == _PAGE


@pytest.mark.parametrize(
    ("text", "max_chars", "expected", "truncated"),
    [
        ("0123456789", 4, "0123", True),
        ("0123456789", 10, "0123456789", False),
        ("0123456789", 11, "0123456789", False),
    ],
    ids=["over-the-cap", "at-the-cap", "under-the-cap"],
)
def test_the_text_is_cut_at_the_cap_and_says_so(
    service: WebFake, text: str, max_chars: int, expected: str, truncated: bool
) -> None:
    _serve(service, {**_REPLY, "markdown": text})

    page = fetch_page_text(_PAGE, max_chars=max_chars)

    assert (page.text, page.truncated) == (expected, truncated)


@pytest.mark.parametrize(
    ("page_url", "error"),
    [
        ("file:///etc/passwd", InvalidURLError),
        ("ftp://example.com/archive", InvalidURLError),
        ("javascript:alert(1)", InvalidURLError),
        ("raw:<html></html>", InvalidURLError),
        ("example.com/no-scheme", InvalidURLError),
        ("http://192.0.2.5/admin", SSRFBlockedError),
        ("http://100.64.0.1/", SSRFBlockedError),
        ("http://127.0.0.1:8080/", SSRFBlockedError),
        ("http://[::1]/", SSRFBlockedError),
        ("http://2130706433/", SSRFBlockedError),
        ("http://localhost/", SSRFBlockedError),
        ("http://169.254.169.254/latest/meta-data", SSRFBlockedError),
        ("http://metadata.google.internal/", SSRFBlockedError),
        ("http://kubernetes.default.svc/", SSRFBlockedError),
        ("http://crawl4ai.devops.svc.cluster.local:11235/token", SSRFBlockedError),
    ],
    ids=lambda value: value if isinstance(value, str) else value.__name__,
)
def test_a_page_url_that_is_not_a_public_web_page_is_refused_before_any_request(
    service: WebFake, otlp: FakeCollector, page_url: str, error: type[Exception]
) -> None:
    with pytest.raises(error) as raised:
        fetch_page_text(page_url)

    assert (raised.type, service.sent, otlp.points(CRAWL4AI_FETCHES_TOTAL.name)) == (
        error,
        [],
        [],
    )


def test_an_empty_service_url_raises_an_error_that_names_the_setting(
    config: Callable[..., Path], keyring_store: FakeKeyring, web: WebFake
) -> None:
    keyring_store.set_password("devops-cli", "crawl4ai_api_token", _TOKEN)
    config(crawl4ai={"url": None})

    with pytest.raises(ConfigurationError) as raised:
        fetch_page_text(_PAGE)

    assert (raised.value.key, "crawl4ai.url" in str(raised.value), web.sent) == (
        "crawl4ai.url",
        True,
        [],
    )


def test_a_missing_token_raises_an_error_that_names_the_credential(
    config: Callable[..., Path], keyring_store: FakeKeyring, web: WebFake
) -> None:
    config(crawl4ai={"url": _SERVICE})

    with pytest.raises(ConfigurationError) as raised:
        fetch_page_text(_PAGE)

    assert (raised.value.key, web.sent) == ("crawl4ai.api_token", [])


def test_a_fetch_counts_ok_and_logs_nothing(
    service: WebFake, otlp: FakeCollector, caplog: pytest.LogCaptureFixture
) -> None:
    _serve(service, _REPLY)

    fetch_page_text(_PAGE)

    assert (otlp.points(CRAWL4AI_FETCHES_TOTAL.name), _warnings(caplog)) == (
        [({"result": "ok"}, 1.0)],
        [],
    )


@pytest.mark.parametrize("status", [401, 403, 429, 500, 504])
def test_a_fetch_the_service_refuses_counts_its_status_and_logs_it_without_the_token_or_query(
    service: WebFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
    status: int,
) -> None:
    _serve(service, {"detail": _PAGE_WITH_QUERY}, status)

    with pytest.raises(PageTextError) as raised:
        fetch_page_text(_PAGE_WITH_QUERY)

    logged = _warnings(caplog)
    leaks = [
        text
        for text in (*logged, str(raised.value), json.dumps(raised.value.details))
        if _TOKEN in text or "private-query-value" in text
    ]
    assert (raised.value.status, otlp.points(CRAWL4AI_FETCHES_TOTAL.name), logged, leaks) == (
        status,
        [({"result": str(status)}, 1.0)],
        [f"A Crawl4AI page fetch failed: the service answered with HTTP {status}."],
        [],
    )


def test_a_redirect_from_the_service_is_not_followed(service: WebFake, otlp: FakeCollector) -> None:
    service.redirect(_MD_URL, "http://attacker.example.com/md", 307)

    with pytest.raises(PageTextError) as raised:
        fetch_page_text(_PAGE)

    assert (raised.value.status, service.requested, otlp.points(CRAWL4AI_FETCHES_TOTAL.name)) == (
        307,
        [_MD_URL],
        [({"result": "307"}, 1.0)],
    )


@pytest.mark.parametrize(
    ("serve", "kind"),
    [
        (lambda web: web.time_out(_MD_URL), "ReadTimeout"),
        (lambda web: web.refuse(_MD_URL), "ConnectError"),
        (lambda web: web.content(_MD_URL, b"<html>not json</html>"), "JSONDecodeError"),
        (lambda web: _serve(web, ["not", "an", "object"]), "the reply is not page text"),
        (lambda web: _serve(web, {"success": True}), "the reply is not page text"),
        (lambda web: _serve(web, {"success": True, "markdown": 7}), "the reply is not page text"),
        (
            lambda web: _serve(web, {**_REPLY, "success": False}),
            "the reply is not page text",
        ),
    ],
    ids=[
        "timeout",
        "refused",
        "not-json",
        "not-an-object",
        "no-markdown",
        "markdown-not-text",
        "success-false",
    ],
)
def test_a_fetch_with_no_answer_or_no_page_text_counts_error_and_logs_the_class(
    service: WebFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
    serve: Callable[[WebFake], None],
    kind: str,
) -> None:
    serve(service)

    with pytest.raises(PageTextError) as raised:
        fetch_page_text(_PAGE_WITH_QUERY)

    assert (
        raised.value.status,
        otlp.points(CRAWL4AI_FETCHES_TOTAL.name),
        _warnings(caplog),
    ) == (
        None,
        [({"result": "error"}, 1.0)],
        [f"A Crawl4AI page fetch failed: {kind}."],
    )


def test_a_reply_over_the_byte_cap_is_refused_and_counted_as_an_error(
    service: WebFake, otlp: FakeCollector
) -> None:
    filler = "x" * DEFAULT_CRAWL4AI_MAX_REPLY_BYTES
    _serve(service, {**_REPLY, "markdown": filler})

    with pytest.raises(PageTextError) as raised:
        fetch_page_text(_PAGE)

    assert (raised.value.status, otlp.points(CRAWL4AI_FETCHES_TOTAL.name)) == (
        None,
        [({"result": "error"}, 1.0)],
    )
