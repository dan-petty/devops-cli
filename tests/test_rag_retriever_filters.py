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
