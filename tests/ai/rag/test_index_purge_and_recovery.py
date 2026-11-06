"""An index run purges what the tree no longer holds, and recovers an index that lost points."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.qdrant import QdrantClientError
from devops_cli.config.constants import CONST_INDEX_CACHE_FILENAME

pytestmark = pytest.mark.usefixtures("keyring_store")


def _indexer(tmp_path: Path, qdrant: Any, embedder: Any) -> WorkspaceIndexer:
    return WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path / ".cache",
    )


def _files_of(qdrant: Any, collection: str, project: str) -> set[str]:
    return {
        point["payload"]["file_path"]
        for point in qdrant.collections.get(collection, [])
        if point["payload"]["project_name"] == project
    }


def _repo(tmp_path: Path, **files: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, text in files.items():
        (repo / name.replace("__", ".")).write_text(text, encoding="utf-8")
    return repo


def test_a_delete_that_fails_is_retried_by_the_next_run(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = _repo(tmp_path, doc__md="# Doc\nSome text.")
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(repo, project="proj-x")
    (repo / "doc.md").unlink()
    qdrant.fail_operation("delete_points_by_files", "delete_points_by_project")

    with pytest.raises(QdrantClientError) as raised:
        indexer.index_workspace(repo, project="proj-x")
    still_stored = _files_of(qdrant, "test_docs", "proj-x")
    qdrant.recover()
    indexer.index_workspace(repo, project="proj-x")

    assert raised.value.error_code == "DEVOPS_CLI_ERROR"
    assert (still_stored, _files_of(qdrant, "test_docs", "proj-x")) == ({"doc.md"}, set())


def test_deleting_every_file_of_a_project_purges_all_its_points(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = _repo(tmp_path, file1__py="def a(): pass\n", file2__py="def b(): pass\n")
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(repo, project="proj-del-all")
    stored = len(qdrant.collections["test_code"])

    (repo / "file1.py").unlink()
    (repo / "file2.py").unlink()
    indexer.index_workspace(repo, project="proj-del-all")

    assert (stored > 0, _files_of(qdrant, "test_code", "proj-del-all")) == (True, set())


def test_a_forced_run_of_one_project_keeps_the_points_of_another(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    for name, source in (("repo-a", "def a(): pass\n"), ("repo-b", "def b(): pass\n")):
        (tmp_path / name).mkdir()
        (tmp_path / name / f"{name[-1]}.py").write_text(source, encoding="utf-8")
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(tmp_path / "repo-a", project="proj-a")
    indexer.index_workspace(tmp_path / "repo-b", project="proj-b")

    indexer.index_workspace(tmp_path / "repo-a", project="proj-a", force=True)
    unchanged = indexer.index_workspace(tmp_path / "repo-b", project="proj-b")

    assert (_files_of(qdrant, "test_code", "proj-a"), _files_of(qdrant, "test_code", "proj-b")) == (
        {"a.py"},
        {"b.py"},
    )
    assert (unchanged["indexed_files"], unchanged["skipped_files"]) == (0, 1)


def test_a_file_deleted_between_two_runs_leaves_no_point_after_a_forced_run(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = _repo(tmp_path, keep__py="def keep(): pass\n", del_me__py="def del_me(): pass\n")
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(repo, project="proj-force-del")

    (repo / "del_me.py").unlink()
    indexer.index_workspace(repo, project="proj-force-del", force=True)

    assert _files_of(qdrant, "test_code", "proj-force-del") == {"keep.py"}


def test_every_delete_waits_for_the_server(tmp_path: Path, qdrant: Any, embedder: Any) -> None:
    repo = _repo(tmp_path, f__py="def f(): pass\n")
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(repo, project="proj-waited")
    (repo / "f.py").unlink()
    indexer.index_workspace(repo, project="proj-waited")
    indexer.index_workspace(repo, project="proj-waited", force=True)

    deletes = [call for call in qdrant.calls if call[0].startswith("delete_points")]

    assert (len(deletes) > 0, {call[2]["wait"] for call in deletes}) == (True, {True})


def test_a_count_that_fails_fails_the_run_and_embeds_nothing(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = _repo(tmp_path, main__py="def main(): pass\n")
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(repo, project="proj-count-fail")
    qdrant.fail_operation("count_points")
    embedded = len(embedder.calls)

    with pytest.raises(QdrantClientError) as raised:
        indexer.index_workspace(repo, project="proj-count-fail")

    assert (raised.value.error_code, len(embedder.calls)) == ("DEVOPS_CLI_ERROR", embedded)


def test_emptying_one_collection_makes_the_next_run_embed_every_file(
    tmp_path: Path, qdrant: Any, embedder: Any, caplog: pytest.LogCaptureFixture
) -> None:
    repo = _repo(tmp_path, main__py="def main(): pass\n", README__md="# README\nHello docs.\n")
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(repo, project="proj-counts")
    qdrant.collections["test_code"] = []

    with caplog.at_level("INFO"):
        stats = indexer.index_workspace(repo, project="proj-counts")

    assert stats["indexed_files"] >= 1
    assert any(
        "proj-counts" in record.message and "test_code" in record.message
        for record in caplog.records
    )
    assert _files_of(qdrant, "test_code", "proj-counts") == {"main.py"}


def test_a_cache_with_no_recorded_counts_over_empty_collections_embeds_every_file(
    tmp_path: Path, qdrant: Any, embedder: Any, caplog: pytest.LogCaptureFixture
) -> None:
    import hashlib

    repo = _repo(tmp_path, main__py="def main(): pass\n")
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(parents=True)
    digest = hashlib.sha256((repo / "main.py").read_bytes()).hexdigest()
    (cache_dir / CONST_INDEX_CACHE_FILENAME).write_text(
        json.dumps({"proj-unrecorded:main.py": digest}), encoding="utf-8"
    )

    with caplog.at_level("INFO"):
        stats = _indexer(tmp_path, qdrant, embedder).index_workspace(
            repo, project="proj-unrecorded"
        )

    assert stats["indexed_files"] >= 1
    assert any("proj-unrecorded" in record.message for record in caplog.records)
    assert _files_of(qdrant, "test_code", "proj-unrecorded") == {"main.py"}


def test_a_cache_write_that_fails_halfway_leaves_the_previous_cache_readable(
    tmp_path: Path, qdrant: Any, embedder: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path, main__py="def main(): pass\n")
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(parents=True)
    cache_file = cache_dir / CONST_INDEX_CACHE_FILENAME
    cache_file.write_text(json.dumps({"proj:existing.py": "hash123"}), encoding="utf-8")
    indexer = _indexer(tmp_path, qdrant, embedder)

    def faulty_replace(src: Any, dst: Any) -> None:
        raise OSError("Disk write failed midway")

    monkeypatch.setattr(os, "replace", faulty_replace)
    with pytest.raises(OSError, match="Disk write failed midway"):
        indexer.index_workspace(repo, project="proj")

    assert json.loads(cache_file.read_text(encoding="utf-8")) == {"proj:existing.py": "hash123"}
