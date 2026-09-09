"""Unit tests for multi-source documentation ingester and SSRF guardrails."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.library.docs_ingester import DocsIngester
from devops_cli.commands.ai import ai_app
from devops_cli.exceptions.ai import DocsIngestionError
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.models.library import DocChunk, IngestDocResult

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
    with pytest.raises((SSRFBlockedError, DocsIngestionError)):
        ingester.ingest_remote_docs("http://192.168.1.1/docs", output_dir=tmp_path)

    with pytest.raises((SSRFBlockedError, DocsIngestionError)):
        ingester.ingest_remote_docs("http://127.0.0.1:8080/docs", output_dir=tmp_path)


def test_ingest_remote_docs_success(tmp_path: Path) -> None:
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

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content
    mock_resp.headers = {"content-type": "text/html"}

    with (
        patch("devops_cli.ai.library.docs_ingester.validate_service_url"),
        patch("httpx2.Client.get", return_value=mock_resp),
    ):
        result = ingester.ingest_remote_docs(
            "https://docs.example.com/api",
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


def test_cli_ai_ingest_docs_remote(tmp_path: Path) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "# Remote Docs\n\nRemote body."
    mock_resp.headers = {"content-type": "text/markdown"}

    with (
        patch("devops_cli.ai.library.docs_ingester.validate_service_url"),
        patch("httpx2.Client.get", return_value=mock_resp),
    ):
        result = runner.invoke(
            ai_app,
            ["ingest", "docs", "https://docs.example.com/guide", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Documentation Ingest" in result.output
