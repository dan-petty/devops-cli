"""Unit tests for the RAG investigation step subsystem."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.rag.investigator import (
    clear_investigation_cache,
    format_rag_investigation_for_prompt,
    investigate_rag_context,
)
from devops_cli.ai.rag.models import CodeChunk, RAGContext, SearchResult
from devops_cli.config.settings import Settings


@pytest.fixture(autouse=True)
def _reset_investigation_cache() -> None:
    clear_investigation_cache()


def test_investigate_rag_context_empty_query() -> None:
    """Empty or whitespace queries return None immediately."""
    assert investigate_rag_context("") is None
    assert investigate_rag_context("   \n\t  ") is None


def test_investigate_rag_context_rag_disabled() -> None:
    """Disabled RAG in configuration returns None without network calls."""
    st = Settings()
    st.ai.rag.enabled = False
    assert investigate_rag_context("architecture design", settings=st) is None


def test_investigate_rag_context_qdrant_unreachable() -> None:
    """Unreachable Qdrant server safely returns None without raising."""
    st = Settings()
    st.ai.rag.enabled = True
    with patch("devops_cli.ai.rag.investigator.QdrantClient") as mock_qdrant_cls:
        mock_instance = MagicMock()
        mock_instance.is_alive.return_value = False
        mock_qdrant_cls.return_value = mock_instance

        res = investigate_rag_context("architecture design", settings=st)
        assert res is None


def test_investigate_rag_context_success() -> None:
    """Successful RAG investigation returns structured RAGContext."""
    st = Settings()
    st.ai.rag.enabled = True

    chunk = CodeChunk(
        id="chk-1",
        file_path="src/devops_cli/ai/client.py",
        project_name="devops-cli",
        language="python",
        start_line=1,
        end_line=50,
        content="class LLMClient: pass",
    )
    search_result = SearchResult(chunk=chunk, score=0.88)

    with (
        patch("devops_cli.ai.rag.investigator.QdrantClient") as mock_qdrant_cls,
        patch("devops_cli.ai.rag.investigator.EmbeddingsEngine") as mock_emb_cls,
        patch("devops_cli.ai.rag.investigator.SemanticRetriever") as mock_retriever_cls,
    ):
        mock_qdrant = MagicMock()
        mock_qdrant.is_alive.return_value = True
        mock_qdrant_cls.return_value = mock_qdrant

        mock_emb = MagicMock()
        mock_emb_cls.return_value = mock_emb

        mock_retriever = MagicMock()
        mock_retriever.retrieve_context.return_value = RAGContext(
            query="LLM client architecture",
            results=[search_result],
            formatted_text="<rag_context><chunk>class LLMClient: pass</chunk></rag_context>",
        )
        mock_retriever_cls.return_value = mock_retriever

        ctx = investigate_rag_context("LLM client architecture", settings=st)
        assert ctx is not None
        assert ctx.has_results is True
        assert len(ctx.results) == 1
        assert "LLMClient" in ctx.formatted_text


def test_investigate_rag_context_persona_expansion() -> None:
    """Persona parameter triggers persona-expanded query retrieval."""
    st = Settings()
    st.ai.rag.enabled = True

    with (
        patch("devops_cli.ai.rag.investigator.QdrantClient") as mock_qdrant_cls,
        patch("devops_cli.ai.rag.investigator.EmbeddingsEngine"),
        patch("devops_cli.ai.rag.investigator.SemanticRetriever") as mock_retriever_cls,
    ):
        mock_qdrant = MagicMock()
        mock_qdrant.is_alive.return_value = True
        mock_qdrant_cls.return_value = mock_qdrant

        mock_retriever = MagicMock()
        mock_retriever.retrieve_context_for_persona.return_value = RAGContext(
            query="security check",
            results=[],
            formatted_text="",
        )
        mock_retriever_cls.return_value = mock_retriever

        ctx = investigate_rag_context("security check", persona="devsecops", settings=st)
        assert ctx is None
        mock_retriever.retrieve_context_for_persona.assert_called_once()


def test_format_rag_investigation_for_prompt() -> None:
    """format_rag_investigation_for_prompt produces clean markdown blocks."""
    assert format_rag_investigation_for_prompt(None) == ""

    empty_ctx = RAGContext(query="test", results=[], formatted_text="")
    assert format_rag_investigation_for_prompt(empty_ctx) == ""

    chunk = CodeChunk(
        id="chk-1",
        file_path="src/main.py",
        project_name="devops-cli",
        language="python",
        start_line=1,
        end_line=10,
        content="def main(): pass",
    )
    ctx = RAGContext(
        query="test",
        results=[SearchResult(chunk=chunk, score=0.9)],
        formatted_text="<rag_context>def main(): pass</rag_context>",
    )
    formatted = format_rag_investigation_for_prompt(ctx, heading="Custom Architecture Context")
    assert "### Custom Architecture Context" in formatted
    assert "<rag_context>def main(): pass</rag_context>" in formatted
