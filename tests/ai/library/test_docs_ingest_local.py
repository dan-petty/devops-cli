"""`DocsIngester.ingest_local_docs`: a folder of Markdown files becomes JSON chunks (#1329)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.ai.library.docs_ingester import DocsIngester
from devops_cli.exceptions.ai import DocsIngestionError
from devops_cli.models.library import IngestDocResult


def test_each_heading_section_of_a_markdown_file_is_a_chunk_file(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "overview.md").write_text(
        "# Architecture Overview\n\nThis is the top-level architecture.\n\n"
        "## Subsystem A\nDetails on Subsystem A.\n\n"
        "## Subsystem B\nDetails on Subsystem B.\n",
        encoding="utf-8",
    )
    (docs_dir / "guide.md").write_text("# User Guide\n\nStep-by-step.\n", encoding="utf-8")
    out_dir = tmp_path / "chunks"

    result = DocsIngester().ingest_local_docs(docs_dir, output_dir=out_dir)

    assert isinstance(result, IngestDocResult)
    assert (
        result.total_pages,
        result.total_chunks >= 3,
        len(list(out_dir.glob("*.json"))) >= 3,
    ) == (2, True, True)


def test_files_of_the_same_name_in_two_folders_keep_separate_chunk_files(tmp_path: Path) -> None:
    for folder, text in (
        ("guide", "# Guide Index\n\nA."),
        ("reference", "# Reference Index\n\nB."),
    ):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "index.md").write_text(text, encoding="utf-8")
    out_dir = tmp_path / "chunks"

    result = DocsIngester().ingest_local_docs(tmp_path, output_dir=out_dir)

    names = {path.name for path in out_dir.glob("*.json")}
    assert (
        result.total_pages,
        any("guide_index" in name for name in names),
        any("reference_index" in name for name in names),
    ) == (2, True, True)


def test_a_missing_folder_is_refused_with_the_path_named(tmp_path: Path) -> None:
    with pytest.raises(DocsIngestionError, match="does not exist"):
        DocsIngester().ingest_local_docs(tmp_path / "nonexistent_folder")
