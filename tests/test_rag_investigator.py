"""Unit tests for the RAG investigation step subsystem."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.ai.rag.investigator import (
    _RAG_STOPPED,
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


def test_a_refused_rag_backend_is_reported_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify a RAG backend the SSRF guard refuses warns once per run, not only at debug."""
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    st = Settings()
    st.ai.rag.enabled = True
    st.qdrant.url = "http://192.0.2.10:6333"

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.investigator"):
        results = [investigate_rag_context(query, settings=st) for query in ("first", "second")]
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.ai.rag.investigator" and record.levelno == logging.WARNING
    ]

    assert (results, ["Refusing non-public Qdrant URL" in message for message in warnings]) == (
        [None, None],
        [True],
    )


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


def test_concurrent_lookups_wait_for_probe_outcome() -> None:
    """20 concurrent lookups against a hanging stub finish in < 1s with at most 2 requests, skipping when probe fails."""
    from concurrent.futures import ThreadPoolExecutor

    clear_investigation_cache()
    st = Settings()
    st.ai.rag.enabled = True

    request_count = 0
    lock = threading.Lock()

    def hanging_embed_query(query: str) -> list[float]:
        nonlocal request_count
        with lock:
            request_count += 1
        time.sleep(0.2)
        raise EmbeddingsError("Timeout hanging query", is_transient=True)

    with (
        patch("devops_cli.ai.rag.investigator.QdrantClient") as mock_qdrant_cls,
        patch("devops_cli.ai.rag.investigator.EmbeddingsEngine") as mock_emb_cls,
        patch("devops_cli.config.settings.get_qdrant_api_key", return_value="test-key"),
        patch("devops_cli.config.settings.get_ai_api_key", return_value="test-key"),
    ):
        mock_qdrant = MagicMock()
        mock_qdrant.is_alive.return_value = True
        mock_qdrant_cls.return_value = mock_qdrant

        mock_emb = MagicMock()
        mock_emb.model = "test-embed"
        mock_emb.embed_query.side_effect = hanging_embed_query
        mock_emb_cls.return_value = mock_emb

        start_t = time.perf_counter()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(investigate_rag_context, f"query {i}", settings=st)
                for i in range(20)
            ]
            results = [f.result() for f in futures]
        elapsed = time.perf_counter() - start_t

        assert (elapsed < 1.0, request_count <= 2, all(r is None for r in results)) == (
            True,
            True,
            True,
        )


def test_concurrent_lookups_healthy_stub_all_get_context() -> None:
    """20 concurrent lookups against a healthy stub all get context."""
    from concurrent.futures import ThreadPoolExecutor

    clear_investigation_cache()
    st = Settings()
    st.ai.rag.enabled = True

    chunk = CodeChunk(
        id="chk-1",
        file_path="src/main.py",
        project_name="devops-cli",
        language="python",
        start_line=1,
        end_line=10,
        content="def hello(): pass",
    )
    search_result = SearchResult(chunk=chunk, score=0.95)

    with (
        patch("devops_cli.ai.rag.investigator.QdrantClient") as mock_qdrant_cls,
        patch("devops_cli.ai.rag.investigator.EmbeddingsEngine") as mock_emb_cls,
        patch("devops_cli.ai.rag.investigator.SemanticRetriever") as mock_retriever_cls,
    ):
        mock_qdrant = MagicMock()
        mock_qdrant.is_alive.return_value = True
        mock_qdrant_cls.return_value = mock_qdrant

        mock_emb = MagicMock()
        mock_emb.model = "test-embed"
        mock_emb_cls.return_value = mock_emb

        mock_retriever = MagicMock()
        mock_retriever.retrieve_context.return_value = RAGContext(
            query="test",
            results=[search_result],
            formatted_text="<rag_context>hello</rag_context>",
        )
        mock_retriever_cls.return_value = mock_retriever

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(investigate_rag_context, f"query {i}", settings=st)
                for i in range(20)
            ]
            results = [f.result() for f in futures]

        assert (len(results), all(r is not None for r in results)) == (20, True)


def test_circuit_breaker_pause_and_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three timeouts open breaker for 60s; lookups during pause send no request; probe after pause resumes."""
    clear_investigation_cache()
    st = Settings()
    st.ai.rag.enabled = True

    simulated_time = 1000.0

    def fake_monotonic() -> float:
        return simulated_time

    monkeypatch.setattr("time.monotonic", fake_monotonic)

    request_count = 0
    fail = True

    def stub_embed_query(query: str) -> list[float]:
        nonlocal request_count
        request_count += 1
        if fail:
            raise EmbeddingsError("Timeout embedding", is_transient=True)
        return [0.1] * 8

    chunk = CodeChunk(
        id="chk-1",
        file_path="src/main.py",
        project_name="devops-cli",
        language="python",
        start_line=1,
        end_line=10,
        content="def hello(): pass",
    )
    search_result = SearchResult(chunk=chunk, score=0.95)

    with (
        patch("devops_cli.ai.rag.investigator.QdrantClient") as mock_qdrant_cls,
        patch("devops_cli.ai.rag.investigator.EmbeddingsEngine") as mock_emb_cls,
        patch("devops_cli.ai.rag.investigator.SemanticRetriever") as mock_retriever_cls,
    ):
        mock_qdrant = MagicMock()
        mock_qdrant.is_alive.return_value = True
        mock_qdrant_cls.return_value = mock_qdrant

        mock_emb = MagicMock()
        mock_emb.model = "test-embed"
        mock_emb.embed_query.side_effect = stub_embed_query
        mock_emb_cls.return_value = mock_emb

        def fake_retrieve_context(q: str, **kwargs: Any) -> RAGContext | None:
            stub_embed_query(q)
            return RAGContext(
                query=q,
                results=[search_result],
                formatted_text="<rag_context>hello</rag_context>",
            )

        mock_retriever = MagicMock()
        mock_retriever.retrieve_context.side_effect = fake_retrieve_context
        mock_retriever_cls.return_value = mock_retriever

        # 1. Three timeouts
        r1 = investigate_rag_context("query 1", settings=st)
        r2 = investigate_rag_context("query 2", settings=st)
        r3 = investigate_rag_context("query 3", settings=st)
        assert (r1, r2, r3, request_count) == (None, None, None, 3)

        # 2. Lookups during 60s pause send 0 requests
        simulated_time += 15.0
        r4 = investigate_rag_context("query 4", settings=st)
        simulated_time += 15.0
        r5 = investigate_rag_context("query 5", settings=st)
        assert (r4, r5, request_count) == (None, None, 3)

        # 3. Probe after pause succeeds and lookups resume
        simulated_time += 40.0
        fail = False
        r6 = investigate_rag_context("query 6", settings=st)
        r7 = investigate_rag_context("query 7", settings=st)
        assert (r6 is not None, r7 is not None, request_count) == (True, True, 5)

        # 4. A 429 counts as transient and does not permanently stop RAG
        fail = True

        def stub_429(query: str, **kwargs: Any) -> RAGContext | None:
            raise EmbeddingsError("429 No deployments available", is_transient=True)

        mock_retriever.retrieve_context.side_effect = stub_429
        r8 = investigate_rag_context("query 8", settings=st)
        assert (r8 is None, not _RAG_STOPPED.is_set()) == (True, True)


def test_settings_score_threshold_reaches_qdrant_search() -> None:
    """Configured ai.rag.score_threshold reaches retriever and Qdrant search."""
    clear_investigation_cache()
    st = Settings()
    st.ai.rag.enabled = True
    st.ai.rag.score_threshold = 0.5

    with (
        patch("devops_cli.ai.rag.investigator.QdrantClient") as mock_qdrant_cls,
        patch("devops_cli.ai.rag.investigator.EmbeddingsEngine") as mock_emb_cls,
        patch("devops_cli.ai.rag.investigator.SemanticRetriever") as mock_retriever_cls,
    ):
        mock_qdrant = MagicMock()
        mock_qdrant.is_alive.return_value = True
        mock_qdrant_cls.return_value = mock_qdrant

        mock_emb = MagicMock()
        mock_emb.model = "test-embed"
        mock_emb_cls.return_value = mock_emb

        mock_retriever = MagicMock()
        mock_retriever.retrieve_context.return_value = None
        mock_retriever_cls.return_value = mock_retriever

        investigate_rag_context("test query", settings=st)

        mock_retriever_cls.assert_called_once()
        _, kwargs = mock_retriever_cls.call_args
        assert kwargs.get("default_score_threshold") == 0.5
