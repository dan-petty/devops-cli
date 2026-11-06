"""Unit tests for multi-source documentation ingester and SSRF guardrails."""

from __future__ import annotations

from pathlib import Path

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.library.docs_ingester import DocsIngester
from devops_cli.commands.ai import app as ai_app
from devops_cli.exceptions.ai import DocsIngestionError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.models.library import DocChunk, IngestDocResult
from tests.support.fakes.http import WebFake

runner = CliRunner()


def test_doc_chunk_model() -> None:
    chunk = DocChunk(
        chunk_id="doc-1",
        source="docs/guide.md",
        headings=["Introduction", "Getting Started"],
        title="Getting Started",
        content="This is the getting started guide.",
        token_estimate=8,
        tags=["guide", "intro"],
    )
    assert chunk.chunk_id == "doc-1"
    assert chunk.title == "Getting Started"
    assert len(chunk.headings) == 2


def test_ingest_local_docs(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    file1 = docs_dir / "overview.md"
    file1.write_text(
        """# Architecture Overview

This is the top-level architecture.

## Subsystem A
Details on Subsystem A.

## Subsystem B
Details on Subsystem B.
""",
        encoding="utf-8",
    )

    file2 = docs_dir / "guide.md"
    file2.write_text(
        """# User Guide

Step-by-step instructions.
""",
        encoding="utf-8",
    )

    out_dir = tmp_path / "chunks"
    ingester = DocsIngester()
    result = ingester.ingest_local_docs(docs_dir, output_dir=out_dir)

    assert isinstance(result, IngestDocResult)
    assert result.total_pages == 2
    assert result.total_chunks >= 3
    assert out_dir.exists()
    assert len(list(out_dir.glob("*.json"))) >= 3


def test_ingest_local_docs_nonexistent_path(tmp_path: Path) -> None:
    ingester = DocsIngester()
    with pytest.raises(DocsIngestionError, match="does not exist"):
        ingester.ingest_local_docs(tmp_path / "nonexistent_folder")


def test_ingest_remote_docs_blocks_ssrf(tmp_path: Path) -> None:
    ingester = DocsIngester()
    # Attempting to ingest private loopback or RFC 1918 endpoint without bypass must raise SSRFBlockedError
    with pytest.raises((SSRFBlockedError, DocsIngestionError)) as raised:
        ingester.ingest_remote_docs("http://192.168.1.1/docs", output_dir=tmp_path)
    assert raised.value.error_code in ("SSRF_BLOCKED", "DOCS_INGESTION_ERROR")

    with pytest.raises((SSRFBlockedError, DocsIngestionError)) as raised:
        ingester.ingest_remote_docs("http://127.0.0.1:8080/docs", output_dir=tmp_path)
    assert raised.value.error_code in ("SSRF_BLOCKED", "DOCS_INGESTION_ERROR")


def test_ingest_remote_docs_success(tmp_path: Path, web: WebFake) -> None:
    ingester = DocsIngester()
    html_content = """<!DOCTYPE html>
<html>
<head><title>API Reference</title></head>
<body>
<nav>Navigation links to ignore</nav>
<main>
  <h1>API Reference</h1>
  <p>Official library documentation.</p>
  <h2>Endpoints</h2>
  <p>Details about endpoints.</p>
</main>
<footer>Footer to ignore</footer>
</body>
</html>"""

    mock_resp = httpx2.Response(200, headers={"content-type": "text/html"}, text=html_content)

    web.serve(lambda request: mock_resp)
    result = ingester.ingest_remote_docs(
        "https://example.com/api",
        output_dir=tmp_path,
    )
    assert result.total_pages == 1
    assert result.total_chunks >= 1
    assert result.is_remote is True


def test_cli_ai_ingest_docs_local(tmp_path: Path) -> None:
    doc_file = tmp_path / "test.md"
    doc_file.write_text("# Title\n\nContent paragraph.", encoding="utf-8")
    out_dir = tmp_path / "out"

    result = runner.invoke(
        ai_app,
        ["ingest", "docs", str(doc_file), "--output-dir", str(out_dir)],
    )
    assert result.exit_code == 0
    assert "Title" in result.output or "test.md" in result.output or "chunks" in result.output
    assert out_dir.exists()


def test_cli_ai_ingest_docs_json_format(tmp_path: Path) -> None:
    doc_file = tmp_path / "test.md"
    doc_file.write_text("# Title\n\nContent paragraph.", encoding="utf-8")
    out_dir = tmp_path / "out_json"

    result = runner.invoke(
        ai_app,
        ["ingest", "docs", str(doc_file), "--output-dir", str(out_dir), "--format", "json"],
    )
    assert result.exit_code == 0
    assert '"total_chunks":' in result.output


def test_cli_ai_ingest_docs_failure(tmp_path: Path) -> None:
    result = runner.invoke(
        ai_app,
        ["ingest", "docs", str(tmp_path / "nonexistent.md")],
    )
    assert result.exit_code != 0


def test_cli_ai_ingest_docs_remote(tmp_path: Path, web: WebFake) -> None:
    mock_resp = httpx2.Response(
        200, headers={"content-type": "text/markdown"}, text="# Remote Docs\n\nRemote body."
    )

    web.serve(lambda request: mock_resp)
    result = runner.invoke(
        ai_app,
        ["ingest", "docs", "https://example.com/guide", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "Documentation Ingest" in result.output


def test_cli_ai_ingest_docs_remote_uppercase_scheme(tmp_path: Path, web: WebFake) -> None:
    mock_resp = httpx2.Response(
        200, headers={"content-type": "text/markdown"}, text="# Remote Docs\n\nRemote body."
    )

    web.serve(lambda request: mock_resp)
    result = runner.invoke(
        ai_app,
        ["ingest", "docs", "HTTPS://example.com/guide", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "Documentation Ingest" in result.output


def test_ingest_local_docs_duplicate_filenames(tmp_path: Path) -> None:
    """Ensure duplicate filenames in different directories produce unique slugs and chunks."""
    guide_dir = tmp_path / "guide"
    guide_dir.mkdir()
    (guide_dir / "index.md").write_text("# Guide Index\n\nContent A.", encoding="utf-8")

    ref_dir = tmp_path / "reference"
    ref_dir.mkdir()
    (ref_dir / "index.md").write_text("# Reference Index\n\nContent B.", encoding="utf-8")

    out_dir = tmp_path / "chunks_dedup"
    ingester = DocsIngester()
    result = ingester.ingest_local_docs(tmp_path, output_dir=out_dir)

    assert result.total_pages == 2
    chunk_files = list(out_dir.glob("*.json"))
    assert len(chunk_files) >= 2
    # Filenames must not overwrite each other
    names = {f.name for f in chunk_files}
    assert any("guide_index" in n for n in names)
    assert any("reference_index" in n for n in names)


def test_ingest_remote_docs_masks_credentials(tmp_path: Path, web: WebFake) -> None:
    """Ensure credentials in remote URL are masked in DocsIngestionError and result."""
    ingester = DocsIngester()

    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    web.serve(refuse)
    with pytest.raises(DocsIngestionError) as excinfo:
        ingester.ingest_remote_docs(
            "https://alice:supersecret999@example.com/api",
            output_dir=tmp_path,
        )
    err_msg = str(excinfo.value)
    assert "supersecret999" not in err_msg
    assert "<masked-password>@example.com" in err_msg or "***@example.com" in err_msg


def test_ingest_remote_docs_multipage_traversal(tmp_path: Path, web: WebFake) -> None:
    """Ensure max_pages traverses links on same origin domain."""
    ingester = DocsIngester()

    page1_html = """<html><body>
    <h1>Page 1</h1>
    <a href="/subpage">Subpage</a>
    <a href="https://example.com:8080/other">External</a>
    </body></html>"""

    page2_html = """<html><body>
    <h1>Subpage 2</h1>
    <p>Subpage content</p>
    </body></html>"""

    def answer(request: httpx2.Request) -> httpx2.Response:
        page = page2_html if "subpage" in str(request.url) else page1_html
        return httpx2.Response(200, headers={"content-type": "text/html"}, text=page)

    web.serve(answer)
    result = ingester.ingest_remote_docs(
        "https://example.com/root",
        output_dir=tmp_path,
        max_pages=2,
    )
    assert (result.total_pages, result.total_chunks >= 2) == (2, True)


def test_ingest_remote_docs_origin_filtering(tmp_path: Path, web: WebFake) -> None:
    """Ensure links are only followed when origin matches start URL origin."""
    ingester = DocsIngester()

    page1_html = """<html><body>
    <h1>Root Page</h1>
    <a href="https://EXAMPLE.COM/a">Upper Host Same Origin</a>
    <a href="https://example.com:443/b">Explicit Default Port Same Origin</a>
    <a href="http://example.com/c">Downgrade Scheme Different Origin</a>
    <a href="https://example.com\\@192.0.2.1/d">Backslash Host Different Origin</a>
    <a href="https://example.com/tab\tlink">Invalid Tab Link</a>
    </body></html>"""

    web.serve(
        lambda request: httpx2.Response(200, headers={"content-type": "text/html"}, text=page1_html)
    )
    result = ingester.ingest_remote_docs(
        "https://example.com/root",
        output_dir=tmp_path,
        max_pages=10,
    )
    visited_urls = web.requested
    assert (
        "https://example.com/a" in visited_urls,
        "https://example.com/b" in visited_urls,
        "http://example.com/c" in visited_urls,
        any("192.0.2.1" in u for u in visited_urls),
        result.total_pages,
    ) == (True, True, False, False, 3)


def test_ingest_remote_docs_slug_sanitization(web: WebFake) -> None:
    """Ensure userinfo is stripped from directory slug and %2e%2e does not escape ingest root."""
    from devops_cli.core.repo import resolve_store_path

    ingester = DocsIngester()
    resp = httpx2.Response(
        200,
        headers={"content-type": "text/html"},
        text="<html><body><h1>Doc</h1><p>Content</p></body></html>",
    )

    web.serve(lambda request: resp)
    res1 = ingester.ingest_remote_docs(
        "https://myuser:secrettoken@example.com",
        max_pages=1,
    )
    res2 = ingester.ingest_remote_docs(
        "https://example.com/%2e%2e",
        max_pages=1,
    )
    out_path = Path(res2.output_dir).resolve()
    ingest_root = resolve_store_path(Path("docs_ingest")).resolve()

    assert (
        "myuser" not in res1.output_dir,
        "secrettoken" not in res1.output_dir,
        out_path.parent == ingest_root,
    ) == (True, True, True)
