"""Unit tests for semantic retriever faceted filters."""

from __future__ import annotations

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.retriever import SemanticRetriever


def test_retriever_faceted_filtering() -> None:
    captured_filters: list[dict | None] = []

    class DummyQdrant(QdrantClient):
        def is_alive(self) -> bool:
            return True

        def search_points(
            self,
            collection_name: str,
            query_vector: list[float],
            limit: int = 5,
            score_threshold: float = 0.35,
            filter_payload: dict | None = None,
        ) -> list[dict]:
            captured_filters.append(filter_payload)
            return [
                {
                    "id": "point-1",
                    "score": 0.88,
                    "payload": {
                        "file_path": "backend/main.go",
                        "start_line": 10,
                        "end_line": 25,
                        "content": "func StartDB() {}",
                        "language": "go",
                        "doc_type": "code",
                        "category": "code",
                        "project_name": "backend-service",
                        "symbol_names": ["StartDB"],
                    },
                }
            ]

    retriever = SemanticRetriever(
        qdrant=DummyQdrant(base_url="http://mock:6333", allow_private_network=True),
        embedder=EmbeddingsEngine(),
    )

    context = retriever.retrieve_context(
        "start database",
        project="backend-service",
        language="go",
        category="code",
    )

    assert context.has_results
    assert len(context.results) == 1
    assert context.results[0].chunk.project_name == "backend-service"
    assert 'project="backend-service"' in context.formatted_text
    assert 'language="go"' in context.formatted_text

    # Verify filter payload was passed to Qdrant search
    assert len(captured_filters) > 0
    assert captured_filters[0] is not None
    assert captured_filters[0]["project_name"] == "backend-service"
    assert captured_filters[0]["language"] == "go"
    assert captured_filters[0]["category"] == "code"


def test_retriever_deduplication_and_validation() -> None:
    from devops_cli.ai.rag.models import CodeChunk, SearchResult

    c1 = CodeChunk(
        id="p1",
        file_path="src/app.py",
        start_line=1,
        end_line=30,
        content="def main():\n    pass\n" * 10,
        language="python",
    )
    # c2 heavily overlaps c1
    c2 = CodeChunk(
        id="p2",
        file_path="src/app.py",
        start_line=5,
        end_line=25,
        content="def main():\n    pass\n" * 8,
        language="python",
    )
    c3 = CodeChunk(
        id="p3",
        file_path="src/utils.py",
        start_line=1,
        end_line=10,
        content="def util(): return 42",
        language="python",
    )

    r1 = SearchResult(chunk=c1, score=0.90)
    r2 = SearchResult(chunk=c2, score=0.85)
    r3 = SearchResult(chunk=c3, score=0.80)

    retriever = SemanticRetriever(
        qdrant=QdrantClient("http://localhost:6333", allow_private_network=True),
        embedder=EmbeddingsEngine(),
    )

    deduped = retriever.filter_and_validate_results([r1, r2, r3], max_chars=10000)
    assert len(deduped) == 2
    assert [d.chunk.id for d in deduped] == ["p1", "p3"]

    # Test character budget truncation
    budget_limited = retriever.filter_and_validate_results([r1, r3], max_chars=50)
    assert len(budget_limited) == 1
    assert budget_limited[0].chunk.id == "p1"
