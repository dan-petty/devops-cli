"""One index holds many projects, each found by its manifest and kept apart by its name."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.indexer import WorkspaceIndexer, detect_project_name
from devops_cli.config.constants import CONST_RAG_KB_PROJECT

pytestmark = pytest.mark.usefixtures("keyring_store")


def _indexer(tmp_path: Path, qdrant: Any, embedder: Any) -> WorkspaceIndexer:
    return WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path / ".cache",
    )


def _projects(qdrant: Any, collection: str) -> set[str]:
    return {point["payload"]["project_name"] for point in qdrant.collections[collection]}


def test_a_file_belongs_to_the_project_of_its_nearest_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repos" / "frontend-app"
    (repo / "src").mkdir(parents=True)
    (repo / "package.json").write_text("{}", encoding="utf-8")
    source = repo / "src" / "index.ts"
    source.write_text("console.log('hi')", encoding="utf-8")

    assert detect_project_name(source, tmp_path) == "frontend-app"


def test_a_workspace_of_several_repos_indexes_each_as_its_own_project(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    (tmp_path / "go-service").mkdir()
    (tmp_path / "go-service" / "go.mod").write_text("module go-service", encoding="utf-8")
    (tmp_path / "go-service" / "main.go").write_text("package main\nfunc Run() {}", "utf-8")
    (tmp_path / "rs-service").mkdir()
    (tmp_path / "rs-service" / "Cargo.toml").write_text('[package]\nname = "rs"', encoding="utf-8")
    (tmp_path / "rs-service" / "lib.rs").write_text("pub fn compute() {}", encoding="utf-8")
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "index.md").write_text("# Team Wiki\nWelcome to internal docs.", "utf-8")

    stats = _indexer(tmp_path, qdrant, embedder).index_workspace(tmp_path)

    assert stats["indexed_files"] >= 3
    assert (stats["code_chunks"] >= 2, stats["doc_chunks"] >= 1) == (True, True)
    assert {"go-service", "rs-service"} <= _projects(qdrant, "test_code")


def test_the_same_file_has_a_different_chunk_id_in_each_project(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    chunker = SemanticChunker()

    first = chunker.chunk_file(readme, relative_to=tmp_path, project_name="project-a")
    second = chunker.chunk_file(readme, relative_to=tmp_path, project_name="project-b")

    assert (len(first) > 0, len(second) > 0, first[0].id != second[0].id) == (True, True, True)


def test_a_readme_of_the_tree_and_one_of_the_knowledge_base_keep_their_own_points(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# Project\n" + "\n".join(f"line {i}" for i in range(1, 50)), encoding="utf-8"
    )

    _indexer(tmp_path, qdrant, embedder).index_workspace(repo, include_kb=True)

    assert {"repo", CONST_RAG_KB_PROJECT} <= _projects(qdrant, "test_docs")


def test_two_projects_with_one_readme_keep_their_points_when_one_is_deleted(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    for name in ("repo-a", "repo-b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "README.md").write_text(
            "# Common Title\nContent common to both repos.", encoding="utf-8"
        )
    indexer = _indexer(tmp_path, qdrant, embedder)
    indexer.index_workspace(tmp_path / "repo-a", project="proj-a")
    indexer.index_workspace(tmp_path / "repo-b", project="proj-b")
    before = _projects(qdrant, "test_docs")

    (tmp_path / "repo-a" / "README.md").unlink()
    indexer.index_workspace(tmp_path / "repo-a", project="proj-a")

    assert (before, _projects(qdrant, "test_docs")) == ({"proj-a", "proj-b"}, {"proj-b"})
