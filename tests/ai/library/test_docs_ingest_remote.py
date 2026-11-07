"""`DocsIngester.ingest_remote_docs`: a crawl of documentation pages, over the web fake (#1329)."""

from __future__ import annotations

from pathlib import Path

import httpx2
import pytest

from devops_cli.ai.library.docs_ingester import DocsIngester
from devops_cli.core.repo import resolve_store_path
from devops_cli.exceptions.ai import DocsIngestionError
from devops_cli.exceptions.security import SSRFBlockedError
from tests.support.fakes.http import WebFake

_HTML = {"content-type": "text/html"}


def _page(body: str) -> httpx2.Response:
    return httpx2.Response(200, headers=_HTML, text=f"<html><body>{body}</body></html>")


def test_a_private_address_is_refused_before_any_request(tmp_path: Path, web: WebFake) -> None:
    ingester = DocsIngester()
    causes = []
    for url in ("http://192.168.1.1/docs", "http://127.0.0.1:8080/docs"):
        with pytest.raises(DocsIngestionError) as raised:
            ingester.ingest_remote_docs(url, output_dir=tmp_path)
        causes.append(type(raised.value.__cause__))

    assert (causes, web.requested) == ([SSRFBlockedError, SSRFBlockedError], [])


def test_a_page_is_reduced_to_its_main_content(tmp_path: Path, web: WebFake) -> None:
    web.serve(
        lambda request: httpx2.Response(
            200,
            headers=_HTML,
            text=(
                "<html><head><title>API Reference</title></head><body>"
                "<nav>Navigation links to ignore</nav>"
                "<main><h1>API Reference</h1><p>Official library documentation.</p>"
                "<h2>Endpoints</h2><p>Details about endpoints.</p></main>"
                "<footer>Footer to ignore</footer></body></html>"
            ),
        )
    )

    result = DocsIngester().ingest_remote_docs("https://example.com/api", output_dir=tmp_path)

    written = "".join(path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.json"))
    assert (
        result.total_pages,
        result.total_chunks >= 1,
        result.is_remote,
        "Official library documentation." in written,
        "Navigation links to ignore" in written,
        "Footer to ignore" in written,
    ) == (1, True, True, True, False, False)


def test_a_markdown_page_is_ingested_as_served(tmp_path: Path, web: WebFake) -> None:
    web.serve(
        lambda request: httpx2.Response(
            200, headers={"content-type": "text/markdown"}, text="# Remote Docs\n\nRemote body."
        )
    )

    result = DocsIngester().ingest_remote_docs("https://example.com/guide", output_dir=tmp_path)

    assert (result.total_pages, result.total_chunks) == (1, 1)


def test_a_failed_request_names_the_url_without_its_password(tmp_path: Path, web: WebFake) -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    web.serve(refuse)

    with pytest.raises(DocsIngestionError) as excinfo:
        DocsIngester().ingest_remote_docs(
            "https://alice:supersecret999@example.com/api", output_dir=tmp_path
        )

    message = str(excinfo.value)
    assert ("supersecret999" in message, "@example.com" in message) == (False, True)


def test_the_crawl_follows_a_link_of_the_same_origin_up_to_max_pages(
    tmp_path: Path, web: WebFake
) -> None:
    def answer(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/subpage":
            return _page("<h1>Subpage 2</h1><p>Subpage content</p>")
        return _page(
            '<h1>Page 1</h1><a href="/subpage">Subpage</a>'
            '<a href="https://example.com:8080/other">Other port</a>'
        )

    web.serve(answer)

    result = DocsIngester().ingest_remote_docs(
        "https://example.com/root", output_dir=tmp_path, max_pages=2
    )

    assert (
        result.total_pages,
        result.total_chunks >= 2,
        "https://example.com/subpage" in web.requested,
    ) == (
        2,
        True,
        True,
    )


def test_the_crawl_follows_only_links_of_the_origin_it_started_on(
    tmp_path: Path, web: WebFake
) -> None:
    web.serve(
        lambda request: _page(
            "<h1>Root Page</h1>"
            '<a href="https://EXAMPLE.COM/a">Upper-case host</a>'
            '<a href="https://example.com:443/b">Explicit default port</a>'
            '<a href="http://example.com/c">Downgraded scheme</a>'
            '<a href="https://example.com\\@192.0.2.1/d">Backslash host</a>'
            '<a href="https://example.com/tab\tlink">Tab in the link</a>'
        )
    )

    result = DocsIngester().ingest_remote_docs(
        "https://example.com/root", output_dir=tmp_path, max_pages=10
    )

    visited = web.requested
    assert (
        "https://example.com/a" in visited,
        "https://example.com/b" in visited,
        "http://example.com/c" in visited,
        any("192.0.2.1" in url for url in visited),
        result.total_pages,
    ) == (True, True, False, False, 3)


def test_the_output_folder_name_has_no_credentials_and_stays_in_the_ingest_root(
    web: WebFake,
) -> None:
    web.serve(lambda request: _page("<h1>Doc</h1><p>Content</p>"))
    ingester = DocsIngester()

    with_credentials = ingester.ingest_remote_docs(
        "https://myuser:secrettoken@example.com", max_pages=1
    )
    dot_dot = ingester.ingest_remote_docs("https://example.com/%2e%2e", max_pages=1)

    ingest_root = resolve_store_path(Path("docs_ingest")).resolve()
    assert (
        "myuser" in with_credentials.output_dir,
        "secrettoken" in with_credentials.output_dir,
        Path(dot_dot.output_dir).resolve().parent == ingest_root,
    ) == (False, False, True)
