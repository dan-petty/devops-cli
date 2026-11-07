"""The semantic retriever's faceted filters, de-duplication and size budget."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.ai.rag.retriever import SemanticRetriever
from tests.support.fakes.qdrant import seed_scored_chunk

pytestmark = pytest.mark.usefixtures("keyring_store")


def _retriever(qdrant: Any, embedder: Any) -> SemanticRetriever:
    return SemanticRetriever(qdrant=qdrant, embedder=embedder)


def test_retriever_faceted_filtering(qdrant: Any, embedder: Any) -> None:
    query_vector = embedder.embed_query("start database")
    seed_scored_chunk(
        qdrant,
        query_vector,
        0.88,
        "func StartDB() {}",
        file_path="backend/main.go",
        language="go",
        doc_type="code",
        category="code",
        project_name="backend-service",
        symbol_names=["StartDB"],
    )
    seed_scored_chunk(
        qdrant,
        query_vector,
        0.95,
        "def start_db(): pass",
        file_path="tools/db.py",
        language="python",
        category="code",
        project_name="tools",
    )

    context = _retriever(qdrant, embedder).retrieve_context(
        "start database",
        project="backend-service",
        language="go",
        category="code",
    )

    assert [(r.chunk.file_path, r.chunk.project_name) for r in context.results] == [
        ("backend/main.go", "backend-service")
    ]
    assert 'project="backend-service"' in context.formatted_text
    assert 'language="go"' in context.formatted_text
    searches = [call for call in qdrant.calls if call[0] == "search_points"]
    assert {tuple(sorted(call[2]["filter_payload"].items())) for call in searches} == {
        (("category", "code"), ("language", "go"), ("project_name", "backend-service"))
    }


def _result(chunk_id: str, file_path: str, start: int, end: int, content: str, score: float):
    chunk = CodeChunk(
        id=chunk_id,
        file_path=file_path,
        start_line=start,
        end_line=end,
        content=content,
        language="python",
    )
    return SearchResult(chunk=chunk, score=score)


def test_a_chunk_that_overlaps_a_better_one_of_the_same_file_is_dropped(
    qdrant: Any, embedder: Any
) -> None:
    results = [
        _result("p1", "src/app.py", 1, 30, "def main():\n    pass\n" * 10, 0.90),
        # p2 lies inside p1.
        _result("p2", "src/app.py", 5, 25, "def main():\n    pass\n" * 8, 0.85),
        _result("p3", "src/utils.py", 1, 10, "def util(): return 42", 0.80),
    ]

    kept = _retriever(qdrant, embedder).filter_and_validate_results(results, max_chars=10000)

    assert [r.chunk.id for r in kept] == ["p1", "p3"]


def test_the_character_budget_stops_the_context(qdrant: Any, embedder: Any) -> None:
    results = [
        _result("p1", "src/app.py", 1, 30, "def main():\n    pass\n" * 10, 0.90),
        _result("p3", "src/utils.py", 1, 10, "def util(): return 42", 0.80),
    ]

    kept = _retriever(qdrant, embedder).filter_and_validate_results(results, max_chars=50)

    assert [r.chunk.id for r in kept] == ["p1"]


def test_visibility_keyword_index_declared() -> None:
    from devops_cli.config.constants import CONST_RAG_PAYLOAD_INDEXES

    names = {idx["field_name"] for idx in CONST_RAG_PAYLOAD_INDEXES}
    assert "visibility" in names
    vis_spec = next(idx for idx in CONST_RAG_PAYLOAD_INDEXES if idx["field_name"] == "visibility")
    assert vis_spec["field_schema"] == "keyword"


def test_retriever_unscoped_search_excludes_private_visibility(
    qdrant: Any, embedder: Any
) -> None:
    query_vector = embedder.embed_query("code")
    seed_scored_chunk(
        qdrant,
        query_vector,
        0.90,
        "def public_code(): pass",
        point_id="p-public",
        file_path="pub.py",
        project_name="org/public-repo",
        visibility="public",
    )
    seed_scored_chunk(
        qdrant,
        query_vector,
        0.90,
        "def secret_code(): pass",
        point_id="p-private",
        file_path="priv.py",
        project_name="org/private-repo",
        visibility="private",
    )
    seed_scored_chunk(
        qdrant,
        query_vector,
        0.90,
        "def local_code(): pass",
        point_id="p-workstation",
        file_path="local.py",
        project_name="local-project",
    )

    retriever = _retriever(qdrant, embedder)

    # 1. Unscoped search (no project specified)
    ctx_unscoped = retriever.retrieve_context("code", project=None)
    returned_ids = [res.chunk.id for res in ctx_unscoped.results]
    assert "p-public" in returned_ids
    assert "p-workstation" in returned_ids
    assert "p-private" not in returned_ids

    # 2. Scoped search specifying private project
    ctx_scoped = retriever.retrieve_context("code", project="org/private-repo")
    scoped_ids = [res.chunk.id for res in ctx_scoped.results]
    assert "p-private" in scoped_ids
    assert "p-public" not in scoped_ids

