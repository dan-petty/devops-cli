"""RAG goes off for the rest of the run when the embedding model is unserved."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.ai.rag.investigator import clear_investigation_cache, investigate_rag_context
from devops_cli.config.settings import Settings
from tests.support.fakes.qdrant import seed_chunk

pytestmark = pytest.mark.usefixtures("keyring_store")

QUERY = "def hello(): pass"


def _settings() -> Settings:
    settings = Settings()
    settings.ai.rag.enabled = True
    settings.qdrant.url = "http://192.0.2.10:6333"
    return settings


def test_an_unserved_model_stops_rag_with_one_warning(
    qdrant: Any, embedder: Any, caplog: pytest.LogCaptureFixture
) -> None:
    embedder.fail("model 'fake-embed-model' is not served")

    with caplog.at_level(logging.WARNING, logger="devops_cli.ai.rag.investigator"):
        results = [investigate_rag_context(f"query {n}", settings=_settings()) for n in (1, 2, 3)]

    warnings = [record.getMessage() for record in caplog.records]
    assert results == [None, None, None]
    assert len(warnings) == 1
    assert "RAG is off for the rest of this run" in warnings[0]
    assert "fake-embed-model" in warnings[0]


def test_a_stopped_rag_sends_no_further_request(qdrant: Any, embedder: Any) -> None:
    embedder.fail("model is not served")
    investigate_rag_context("query 1", settings=_settings())
    embedder.recover()
    seed_chunk(qdrant, embedder, QUERY)
    searches = len([call for call in qdrant.calls if call[0] == "search_points"])

    later = investigate_rag_context(QUERY, settings=_settings())

    assert (later, len([c for c in qdrant.calls if c[0] == "search_points"])) == (None, searches)


def test_clearing_the_cache_lifts_the_stop(qdrant: Any, embedder: Any) -> None:
    embedder.fail("model is not served")
    investigate_rag_context("query 1", settings=_settings())
    embedder.recover()
    seed_chunk(qdrant, embedder, QUERY)

    clear_investigation_cache()
    context = investigate_rag_context(QUERY, settings=_settings())

    assert context is not None
    assert [result.chunk.content for result in context.results] == [QUERY]


def test_a_transient_failure_does_not_stop_rag(qdrant: Any, embedder: Any) -> None:
    seed_chunk(qdrant, embedder, QUERY)
    embedder.fail_next(EmbeddingsError("429 slow down", is_transient=True))

    skipped = investigate_rag_context(QUERY, settings=_settings())
    served = investigate_rag_context(f"{QUERY} again", settings=_settings())

    assert (skipped, served is not None) == (None, True)
