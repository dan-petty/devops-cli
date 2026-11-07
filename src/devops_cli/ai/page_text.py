"""The text of a web page, from the Crawl4AI service (#3887).

`fetch_page_text` sends `POST {crawl4ai.url}/md` with the page URL and the bearer token. The service
loads the page in a browser, so a page that needs JavaScript gives its text too. A model chooses the
page URL, so this module is a boundary:

- The page URL is checked before any request: http or https only, and no host that
  `is_loopback_or_private_host` refuses (a private, loopback or link-local address, a cloud metadata
  name, or a name that is not a public DNS name). The service checks the address it dials again.
- The client dials the service only, at the private egress level, and follows no redirect.
- The client reads at most `DEFAULT_CRAWL4AI_MAX_REPLY_BYTES` of a reply, and cuts the text at
  `max_chars`.
- The text is data from the web. It is untrusted: the caller must never run it as an instruction.
- The token goes only to the origin that `crawl4ai.url` names. A log line and an error hold the
  status or the class of a failure, and never the token or the page URL.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx2
from pydantic import AwareDatetime, BaseModel, ConfigDict

from devops_cli.config.constants import CONST_CRAWL4AI_RESULT_ERROR, CONST_CRAWL4AI_RESULT_OK
from devops_cli.config.defaults import (
    DEFAULT_CRAWL4AI_MAX_REPLY_BYTES,
    DEFAULT_CRAWL4AI_TIMEOUT_SECONDS,
    DEFAULT_PAGE_TEXT_MAX_CHARS,
)
from devops_cli.config.settings import Settings, get_crawl4ai_api_token, load_settings
from devops_cli.core.validation import is_loopback_or_private_host
from devops_cli.exceptions.ai import PageTextError
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.exceptions.validation import InvalidURLError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client, request_headers
from devops_cli.http.urls import service_base_url
from devops_cli.telemetry.instruments import CRAWL4AI_FETCHES_TOTAL, emit

logger = logging.getLogger(__name__)

_URL_SETTING = "crawl4ai.url"
_CREDENTIAL = "crawl4ai.api_token"
_NOT_PAGE_TEXT = "the reply is not page text"
_OVER_THE_CAP = "the reply is larger than the byte cap"


class PageText(BaseModel):
    """The text of one page, as Markdown.

    `source_url` is the URL that the caller asked for, never one that the reply names. `text` is
    untrusted data from the web. `truncated` is true when the text was cut at the cap.
    """

    model_config = ConfigDict(frozen=True)

    source_url: str
    text: str
    fetched_at: AwareDatetime
    truncated: bool


def fetch_page_text(
    url: str,
    *,
    max_chars: int = DEFAULT_PAGE_TEXT_MAX_CHARS,
    settings: Settings | None = None,
) -> PageText:
    """Fetch the text of the page at `url` through the Crawl4AI service.

    Each fetch that reaches the service adds 1 to `devops_cli_crawl4ai_fetches_total` by its result:
    `ok`, the HTTP status of a fetch that the service refused, or `error`. A failed fetch logs one
    warning that names the status or the class of the failure.

    Raises `InvalidURLError` for a page URL that is not http or https, `SSRFBlockedError` for a
    host that is not a public web host, `ConfigurationError` when `crawl4ai.url` or the token is
    not set, and `PageTextError` for a failed fetch.
    """
    page_url = checked_page_url(url)
    active = settings or load_settings()
    service = crawl4ai_service(active)
    token = get_crawl4ai_api_token(active)
    if not token:
        raise ConfigurationError(f"The credential {_CREDENTIAL} is not set", key=_CREDENTIAL)
    text = _markdown(service, token, page_url)
    return PageText(
        source_url=page_url,
        text=text[:max_chars],
        fetched_at=datetime.now(UTC),
        truncated=len(text) > max_chars,
    )


def crawl4ai_service(settings: Settings) -> str:
    """The base URL of the Crawl4AI service, or the `ConfigurationError` that names the setting."""
    if not settings.crawl4ai.url:
        raise ConfigurationError(f"The setting {_URL_SETTING} is not set", key=_URL_SETTING)
    return service_base_url(settings.crawl4ai.url, _URL_SETTING)


def checked_page_url(url: str) -> str:
    """`url` when it is an http or https URL with a host that may be fetched, else the refusal."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError as exc:
        raise InvalidURLError(url, reason="The page URL cannot be read") from exc
    if parts.scheme not in ("http", "https") or not host:
        raise InvalidURLError(url, reason="Only http and https page URLs may be fetched")
    if is_loopback_or_private_host(host):
        raise SSRFBlockedError(url, reason="the page is not on a public web host")
    return url


def _markdown(service: str, token: str, page_url: str) -> str:
    """The Markdown that one `POST /md` gives. It counts the fetch by its result, and logs a failed
    one."""
    try:
        text = _post(service, token, page_url)
    except PageTextError as exc:
        emit(
            CRAWL4AI_FETCHES_TOTAL,
            1,
            {"result": CONST_CRAWL4AI_RESULT_ERROR if exc.status is None else str(exc.status)},
        )
        logger.warning("%s", exc.message)
        raise
    emit(CRAWL4AI_FETCHES_TOTAL, 1, {"result": CONST_CRAWL4AI_RESULT_OK})
    return text


def _post(service: str, token: str, page_url: str) -> str:
    """One `POST /md` and the Markdown of its reply, or the `PageTextError` that tells why not."""
    try:
        with (
            http_client(
                level=EgressLevel.PRIVATE, read_timeout=DEFAULT_CRAWL4AI_TIMEOUT_SECONDS
            ) as client,
            client.stream(
                "POST",
                f"{service}/md",
                json={"url": page_url, "f": "fit"},
                headers=request_headers({"Authorization": f"Bearer {token}"}),
            ) as response,
        ):
            if not response.is_success:
                status = response.status_code
                raise PageTextError(f"the service answered with HTTP {status}", status=status)
            body = _read_capped(response)
        reply = json.loads(body)
    except (httpx2.HTTPError, ValueError) as exc:
        raise PageTextError(type(exc).__name__) from exc
    if not isinstance(reply, dict) or reply.get("success") is not True:
        raise PageTextError(_NOT_PAGE_TEXT)
    markdown = reply.get("markdown")
    if not isinstance(markdown, str):
        raise PageTextError(_NOT_PAGE_TEXT)
    return markdown


def _read_capped(response: httpx2.Response) -> bytes:
    """The decoded body of a streamed reply, refused as soon as it passes the byte cap."""
    body = bytearray()
    for chunk in response.iter_bytes():
        body += chunk
        if len(body) > DEFAULT_CRAWL4AI_MAX_REPLY_BYTES:
            raise PageTextError(_OVER_THE_CAP)
    return bytes(body)
