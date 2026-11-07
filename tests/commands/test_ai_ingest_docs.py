"""`devops ai ingest docs`: arguments, output and exit codes, over the web fake (#1329)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from tests.support.fakes.http import WebFake


def _doc_file(tmp_path: Path) -> Path:
    doc_file = tmp_path / "test.md"
    doc_file.write_text("# Title\n\nContent paragraph.", encoding="utf-8")
    return doc_file


def test_a_local_file_is_ingested_into_the_output_folder(
    cli: Callable[..., Any], tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"

    result = cli("ai", "ingest", "docs", _doc_file(tmp_path), "--output-dir", out_dir)

    assert (result.exit_code, "Documentation Ingest" in result.output, out_dir.is_dir()) == (
        0,
        True,
        True,
    )


def test_the_json_format_prints_the_result_as_json(cli: Callable[..., Any], tmp_path: Path) -> None:
    result = cli(
        "ai",
        "ingest",
        "docs",
        _doc_file(tmp_path),
        "--output-dir",
        tmp_path / "out",
        "--format",
        "json",
    )

    assert (result.exit_code, '"total_chunks":' in result.output) == (0, True)


def test_a_missing_path_exits_with_an_error(cli: Callable[..., Any], tmp_path: Path) -> None:
    result = cli("ai", "ingest", "docs", tmp_path / "nonexistent.md")

    assert result.exit_code != 0


@pytest.mark.parametrize("scheme", ["https", "HTTPS"])
def test_a_url_is_fetched_whatever_the_case_of_its_scheme(
    cli: Callable[..., Any], tmp_path: Path, web: WebFake, scheme: str
) -> None:
    web.serve(
        lambda request: httpx2.Response(
            200, headers={"content-type": "text/markdown"}, text="# Remote Docs\n\nRemote body."
        )
    )

    result = cli("ai", "ingest", "docs", f"{scheme}://example.com/guide", "--output-dir", tmp_path)

    assert (result.exit_code, "Documentation Ingest" in result.output, len(web.requested)) == (
        0,
        True,
        1,
    )
