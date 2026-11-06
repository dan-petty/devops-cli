"""What a RAG investigation returns for a query, over the Qdrant and embedder fakes."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.ai.rag.investigator import (
    clear_investigation_cache,
    format_rag_investigation_for_prompt,
    investigate_rag_context,
)
from devops_cli.ai.rag.models import CodeChunk, RAGContext, SearchResult
from devops_cli.config.settings import Settings
from tests.support.fakes.qdrant import seed_chunk

pytestmark = pytest.mark.usefixtures("keyring_store")

QUERY = "class LLMClient: pass"


def _settings() -> Settings:
    settings = Settings()
    settings.ai.rag.enabled = True
    settings.qdrant.url = "http://192.0.2.10:6333"
    return settings


def _searches(qdrant: Any) -> list[tuple[str, tuple[Any, ...], dict[str, Any]]]:
    return [call for call in qdrant.calls if call[0] == "search_points"]


def test_an_empty_query_gets_no_context(qdrant: Any, embedder: Any) -> None:
    assert (investigate_rag_context(""), investigate_rag_context("   \n\t  ")) == (None, None)
    assert (qdrant.calls, embedder.calls) == ([], [])


def test_a_disabled_rag_sends_no_request(qdrant: Any, embedder: Any) -> None:
    settings = _settings()
    settings.ai.rag.enabled = False

    assert investigate_rag_context("architecture design", settings=settings) is None
    assert (qdrant.calls, embedder.calls) == ([], [])


def test_an_unreachable_qdrant_gets_no_context_and_no_embedding(qdrant: Any, embedder: Any) -> None:
    qdrant.refusing = True

    assert investigate_rag_context("architecture design", settings=_settings()) is None
    assert embedder.calls == []


def test_a_refused_rag_backend_is_reported_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A backend the SSRF guard refuses warns once per run, not only at debug."""
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)

    with caplog.at_level(logging.DEBUG, logger="devops_cli.ai.rag.investigator"):
        results = [
            investigate_rag_context(query, settings=_settings()) for query in ("first", "second")
        ]
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.name == "devops_cli.ai.rag.investigator" and record.levelno == logging.WARNING
    ]

    assert (results, ["SSRF blocked" in message for message in warnings]) == (
        [None, None],
        [True],
    )


def test_a_matching_chunk_is_returned_as_grounding_context(qdrant: Any, embedder: Any) -> None:
    seed_chunk(qdrant, embedder, QUERY, file_path="src/devops_cli/ai/client.py")

    ctx = investigate_rag_context(QUERY, settings=_settings())

    assert ctx is not None
    assert [r.chunk.file_path for r in ctx.results] == ["src/devops_cli/ai/client.py"]
    assert "class LLMClient: pass" in ctx.formatted_text
    assert {call[1][0] for call in _searches(qdrant)} == {"devops_code", "devops_docs"}


def test_a_query_that_matches_no_chunk_gets_no_context(qdrant: Any, embedder: Any) -> None:
    qdrant.ensure_collection("devops_code", 4)

    assert investigate_rag_context(QUERY, settings=_settings()) is None


def test_a_persona_expands_the_query_that_is_embedded(qdrant: Any, embedder: Any) -> None:
    investigate_rag_context("security check", persona="devsecops", settings=_settings())

    (embedded, is_query) = embedder.calls[0]
    assert (embedded[0].startswith("security check"), "secrets" in embedded[0], is_query) == (
        True,
        True,
        True,
    )


def test_the_score_threshold_of_the_settings_reaches_the_search(qdrant: Any, embedder: Any) -> None:
    settings = _settings()
    settings.ai.rag.score_threshold = 0.5

    investigate_rag_context("test query", settings=settings)

    assert {call[2]["score_threshold"] for call in _searches(qdrant)} == {0.5}


def test_a_given_top_k_limits_the_results(qdrant: Any, embedder: Any) -> None:
    for number in range(4):
        seed_chunk(qdrant, embedder, QUERY, file_path=f"src/mod{number}.py")

    ctx = investigate_rag_context(QUERY, settings=_settings(), top_k=2)

    assert ctx is not None
    assert len(ctx.results) == 2


def test_a_repeated_query_is_served_from_the_cache(qdrant: Any, embedder: Any) -> None:
    seed_chunk(qdrant, embedder, QUERY)
    settings = _settings()

    first = investigate_rag_context(QUERY, settings=settings)
    searches = len(_searches(qdrant))
    second = investigate_rag_context(QUERY, settings=settings)

    assert (first is not None, second is first, len(_searches(qdrant))) == (True, True, searches)


def test_an_empty_lookup_is_cached(qdrant: Any, embedder: Any) -> None:
    settings = _settings()

    results = [investigate_rag_context("empty query", settings=settings) for _ in range(2)]

    assert (results, len(embedder.calls)) == ([None, None], 1)


def test_a_transient_failure_is_not_cached(qdrant: Any, embedder: Any) -> None:
    seed_chunk(qdrant, embedder, QUERY)
    embedder.fail_next(EmbeddingsError("Timeout embedding", is_transient=True))
    settings = _settings()

    first = investigate_rag_context(QUERY, settings=settings)
    second = investigate_rag_context(QUERY, settings=settings)

    assert (first, second is not None) == (None, True)


def test_clearing_the_cache_runs_the_lookup_again(qdrant: Any, embedder: Any) -> None:
    settings = _settings()
    investigate_rag_context("empty query", settings=settings)

    clear_investigation_cache()
    investigate_rag_context("empty query", settings=settings)

    assert len(embedder.calls) == 2


def test_the_prompt_block_is_empty_without_results() -> None:
    empty = RAGContext(query="test", results=[], formatted_text="")

    assert (
        format_rag_investigation_for_prompt(None),
        format_rag_investigation_for_prompt(empty),
    ) == (
        "",
        "",
    )


def test_the_prompt_block_carries_the_heading_and_the_context() -> None:
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

    assert formatted == (
        "\n\n### Custom Architecture Context\n<rag_context>def main(): pass</rag_context>\n"
    )
