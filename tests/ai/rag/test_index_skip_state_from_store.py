"""An index run with no cache file reads what the store already holds, as a new pod of the ingest
does, and embeds only the files whose content the store does not hold (#7467)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.qdrant import QdrantClientError

pytestmark = pytest.mark.usefixtures("keyring_store")

_PROJECT = "example/app"


def _indexer(cache_dir: Path, qdrant: Any, embedder: Any) -> WorkspaceIndexer:
    """An indexer with its own cache folder, as each pod of the ingest has an empty one."""
    return WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, text in files.items():
        (repo / name).write_text(text, encoding="utf-8")
    return repo


def _embedded_since(embedder: Any, start: int) -> list[str]:
    return [text for texts, _ in embedder.calls[start:] for text in texts]


def _upserts_since(qdrant: Any, start: int) -> list[Any]:
    return [call for call in qdrant.calls[start:] if call[0] == "upsert_points"]


def _stored_ids(qdrant: Any, file_path: str) -> set[str]:
    return {
        point["id"]
        for points in qdrant.collections.values()
        for point in points
        if point["payload"].get("file_path") == file_path
    }


def _chunks(indexer: WorkspaceIndexer, repo: Path, name: str) -> list[Any]:
    return indexer.chunker.chunk_file(
        repo / name, relative_to=repo.resolve(), project_name=_PROJECT
    )


def _unchanged_run(skipped: int, removed: int = 0) -> dict[str, Any]:
    return {
        "indexed_files": 0,
        "files_indexed": 0,
        "total_chunks": 0,
        "chunks_indexed": 0,
        "code_chunks": 0,
        "doc_chunks": 0,
        "removed_files": removed,
        "pruned_chunks": removed,
        "skipped_files": skipped,
        "collections": ["test_code", "test_docs"],
    }


def test_each_point_holds_the_hash_and_the_chunk_count_of_its_file(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    text = "def first():\n    return 1\n\n\ndef second():\n    return 2\n"
    repo = _repo(tmp_path, {"two.py": text})

    _indexer(tmp_path / "pod-1", qdrant, embedder).index_workspace(repo, project=_PROJECT)

    points = qdrant.collections["test_code"]
    assert [(p["payload"]["file_hash"], p["payload"]["file_chunks"]) for p in points] == [
        (hashlib.sha256(text.encode("utf-8")).hexdigest(), 2)
    ] * 2


def test_a_run_with_no_cache_file_embeds_no_file_that_the_store_holds(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = _repo(
        tmp_path,
        {"main.py": "def main():\n    return 1\n", "README.md": "# App\nHow to run it.\n"},
    )
    _indexer(tmp_path / "pod-1", qdrant, embedder).index_workspace(repo, project=_PROJECT)
    embedded, requests = len(embedder.calls), len(qdrant.calls)

    second = _indexer(tmp_path / "pod-2", qdrant, embedder).index_workspace(repo, project=_PROJECT)

    assert second == _unchanged_run(skipped=2)
    assert (_embedded_since(embedder, embedded), _upserts_since(qdrant, requests)) == ([], [])


def test_a_run_with_no_cache_file_embeds_only_the_edited_file_and_drops_its_old_points(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = _repo(
        tmp_path,
        {"a.py": "def a():\n    return 1\n", "b.py": "def b():\n    return 2\n"},
    )
    _indexer(tmp_path / "pod-1", qdrant, embedder).index_workspace(repo, project=_PROJECT)
    b_points = _stored_ids(qdrant, "b.py")
    (repo / "a.py").write_text(
        "# Edited.\n\n\ndef a():\n    return 10\n\n\ndef a_two():\n    return 20\n",
        encoding="utf-8",
    )
    embedded = len(embedder.calls)
    indexer = _indexer(tmp_path / "pod-2", qdrant, embedder)

    second = indexer.index_workspace(repo, project=_PROJECT)

    new_chunks = _chunks(indexer, repo, "a.py")
    assert (second["indexed_files"], second["skipped_files"]) == (1, 1)
    assert sorted(_embedded_since(embedder, embedded)) == sorted(c.content for c in new_chunks)
    assert _stored_ids(qdrant, "a.py") == {c.id for c in new_chunks}
    assert _stored_ids(qdrant, "b.py") == b_points


def test_points_with_no_file_hash_are_embedded_once_then_skipped(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """Points that a release before #7467 wrote hold no file hash: the first run embeds each file
    of them once, and a later run with no cache file skips it."""
    repo = _repo(
        tmp_path,
        {"main.py": "def main():\n    return 1\n", "README.md": "# App\nHow to run it.\n"},
    )
    first = _indexer(tmp_path / "pod-1", qdrant, embedder).index_workspace(repo, project=_PROJECT)
    for points in qdrant.collections.values():
        for point in points:
            point["payload"].pop("file_hash", None)
            point["payload"].pop("file_chunks", None)

    second = _indexer(tmp_path / "pod-2", qdrant, embedder).index_workspace(repo, project=_PROJECT)
    embedded = len(embedder.calls)
    third = _indexer(tmp_path / "pod-3", qdrant, embedder).index_workspace(repo, project=_PROJECT)

    assert (second["indexed_files"], second["total_chunks"]) == (2, first["total_chunks"])
    assert (third, _embedded_since(embedder, embedded)) == (_unchanged_run(skipped=2), [])


def test_a_run_with_no_cache_file_drops_the_points_of_a_deleted_file(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = _repo(
        tmp_path,
        {"a.py": "def a():\n    return 1\n", "b.py": "def b():\n    return 2\n"},
    )
    _indexer(tmp_path / "pod-1", qdrant, embedder).index_workspace(repo, project=_PROJECT)
    (repo / "b.py").unlink()

    second = _indexer(tmp_path / "pod-2", qdrant, embedder).index_workspace(repo, project=_PROJECT)

    assert (second, _stored_ids(qdrant, "b.py")) == (_unchanged_run(skipped=1, removed=1), set())


def test_a_store_read_that_fails_stops_the_run_before_any_embed(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = _repo(tmp_path, {"main.py": "def main():\n    return 1\n"})
    _indexer(tmp_path / "pod-1", qdrant, embedder).index_workspace(repo, project=_PROJECT)
    qdrant.fail_operation("scroll_payloads")
    embedded = len(embedder.calls)

    with pytest.raises(QdrantClientError) as raised:
        _indexer(tmp_path / "pod-2", qdrant, embedder).index_workspace(repo, project=_PROJECT)

    assert (raised.value.error_code, _embedded_since(embedder, embedded)) == (
        "DEVOPS_CLI_ERROR",
        [],
    )


def test_a_run_with_its_cache_file_reads_no_store_state(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    """The cache file of a workstation still skips each unchanged file with no store read."""
    repo = _repo(tmp_path, {"main.py": "def main():\n    return 1\n"})
    indexer = _indexer(tmp_path / "workstation", qdrant, embedder)
    indexer.index_workspace(repo, project=_PROJECT)
    requests = len(qdrant.calls)

    second = indexer.index_workspace(repo, project=_PROJECT)

    reads = [call for call in qdrant.calls[requests:] if call[0] == "scroll_payloads"]
    assert (second, reads) == (_unchanged_run(skipped=1), [])
