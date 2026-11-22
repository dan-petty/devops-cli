"""Indexing a workspace into Qdrant, and searching what was indexed, over the edge fakes."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.retriever import SemanticRetriever
from tests.support.fakes.process import ProcessAnswer, ProcessFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def _indexer(tmp_path: Path, qdrant: Any, embedder: Any) -> WorkspaceIndexer:
    return WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")


def _indexed_files(qdrant: Any) -> set[str]:
    return {
        point["payload"]["file_path"] for points in qdrant.collections.values() for point in points
    }


def test_indexing_stores_files_skips_unchanged_ones_and_purges_deleted_ones(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def run_app():\n    print('app running')\n", encoding="utf-8")
    doc_file = tmp_path / "README.md"
    doc_file.write_text("# App Documentation\nHow to run app.\n", encoding="utf-8")
    indexer = _indexer(tmp_path, qdrant, embedder)

    first = indexer.index_workspace(tmp_path)
    second = indexer.index_workspace(tmp_path)
    doc_file.unlink()
    third = indexer.index_workspace(tmp_path)

    assert (first["indexed_files"], first["removed_files"]) == (2, 0)
    assert first["total_chunks"] >= 2
    assert (second["indexed_files"], second["skipped_files"], second["removed_files"]) == (0, 2, 0)
    assert (third["indexed_files"], third["skipped_files"], third["removed_files"]) == (0, 1, 1)
    assert qdrant.collections[indexer.docs_collection] == []


def test_a_search_finds_what_was_indexed(tmp_path: Path, qdrant: Any, embedder: Any) -> None:
    (tmp_path / "app.py").write_text("def run_app():\n    print('app running')\n", encoding="utf-8")
    _indexer(tmp_path, qdrant, embedder).index_workspace(tmp_path)

    retriever = SemanticRetriever(qdrant=qdrant, embedder=embedder)
    results = retriever.search("how to run app", top_k=5)
    context = retriever.retrieve_context("how to run app")

    assert any("app" in r.chunk.content for r in results)
    assert (context.has_results, "<rag_context>" in context.formatted_text) == (True, True)


def test_indexing_the_workspace_and_the_knowledge_base_do_not_purge_each_other(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('hello workspace')", encoding="utf-8")
    indexer = _indexer(tmp_path, qdrant, embedder)

    workspace_stats = indexer.index_workspace(workspace, project="my-workspace")
    code_points = len(qdrant.collections[indexer.code_collection])
    kb_stats = indexer.index_knowledge_base()
    workspace_again = indexer.index_workspace(workspace, project="my-workspace")

    assert workspace_stats["indexed_files"] == 1
    assert (kb_stats["indexed_files"] > 0, kb_stats["removed_files"]) == (True, 0)
    assert len(qdrant.collections[indexer.code_collection]) == code_points
    assert workspace_again["removed_files"] == 0
    assert len(qdrant.collections[indexer.docs_collection]) >= 1


def test_indexing_skips_ignored_lock_and_hidden_files(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """Only source and documents are indexed: not .gitignore matches, lockfiles or hidden files."""
    (tmp_path / ".gitignore").write_text("*.tmp\nbuild/\n", encoding="utf-8")
    kept = {"main.py": "print('hi')", "Dockerfile": "FROM alpine"}
    skipped = {
        "test.tmp": "temp",
        "uv.lock": "lock",
        "Cargo.lock": "lock",
        "poetry.lock": "lock",
        "package-lock.json": "lock",
        "pnpm-lock.yaml": "lock",
        "go.sum": "lock",
        ".hidden.py": "print('hidden')",
    }
    for name, text in {**kept, **skipped}.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.py").write_text("print('built')", encoding="utf-8")

    _indexer(tmp_path, qdrant, embedder).index_workspace(tmp_path, include_kb=False)

    assert _indexed_files(qdrant) == set(kept)


def test_indexing_skips_vendored_files_and_keeps_generated_ones(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """A file that the work tree's `.gitattributes` mark vendored is the data of a third party,
    not text to search: the tiktoken vocabularies gave thousands of chunks and stopped a full
    index. A generated file, such as the command reference, is a document to search (#6717)."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitattributes").write_text(
        "*.tiktoken linguist-vendored\n"
        "reference.md linguist-generated\n"
        "kept.py linguist-vendored=false\n",
        encoding="utf-8",
    )
    for name in ("main.py", "vocab.tiktoken", "kept.py"):
        (tmp_path / name).write_text(f"print('{name}')\n", encoding="utf-8")
    (tmp_path / "reference.md").write_text(
        "# devops ai rag index\n\nIndex the workspace.\n", encoding="utf-8"
    )

    _indexer(tmp_path, qdrant, embedder).index_workspace(tmp_path, include_kb=False)

    assert _indexed_files(qdrant) == {"main.py", "kept.py", "reference.md"}


def _answer_work_tree(process_fake: ProcessFake, root: Path, attributes: str) -> None:
    """Answer the git reads of a walk of `root`: a work tree, and the `check-attr` output."""
    process_fake.answer(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        ProcessAnswer(stdout=f"{root}\n"),
    )
    process_fake.answer(["git", "-C", str(root), "check-attr"], ProcessAnswer(stdout=attributes))


def test_one_git_call_reads_the_attributes_of_all_files(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    root = tmp_path.resolve()
    for name in ("a.py", "b.py", "c.py"):
        (root / name).write_text(f"print('{name}')\n", encoding="utf-8")
    _answer_work_tree(
        process_fake,
        root,
        "a.py\0linguist-vendored\0unspecified\0"
        "b.py\0linguist-vendored\0set\0"
        "c.py\0linguist-vendored\0false\0",
    )

    files = WorkspaceIndexer.collect_files(root)

    attribute_reads = [call for call in process_fake.calls if "check-attr" in call.argv]
    assert [(call.argv[3:], call.stdin) for call in attribute_reads] == [
        (
            ("check-attr", "-z", "--stdin", "linguist-vendored"),
            "a.py\0b.py\0c.py\0",
        )
    ]
    assert [path.name for path in files] == ["a.py", "c.py"]


def test_a_directory_with_no_repository_starts_no_attribute_read(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    root = tmp_path.resolve()
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    process_fake.answer(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        ProcessAnswer(returncode=128, stderr="fatal: not a git repository\n"),
    )

    files = WorkspaceIndexer.collect_files(root)

    assert [call.argv for call in process_fake.calls if "check-attr" in call.argv] == []
    assert [path.name for path in files] == ["main.py"]


def test_collect_files_finds_nothing_under_a_missing_directory(tmp_path: Path) -> None:
    assert WorkspaceIndexer.collect_files(tmp_path / "nonexistent") == []


def test_the_stats_count_the_vectors_of_each_collection(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(tmp_path, include_kb=False)

    stats = {stat.collection_name: stat for stat in indexer.get_stats()}

    assert stats[indexer.code_collection].total_vectors == len(
        qdrant.collections[indexer.code_collection]
    )
