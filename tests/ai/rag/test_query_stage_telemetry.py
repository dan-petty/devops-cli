"""RAG query latency is timed by stage, and its histogram reaches past the query's timeouts (#975).

The RAG latency panel flattened at 5 s, the histogram's top bucket, though a query waits up to
30 s for the gateway's embedding and waited up to an hour for each Qdrant request, and nothing
split a query's time between embedding, the Qdrant searches and ranking. The metrics are read
from the OTLP fake.
"""

from __future__ import annotations

from typing import Any

import httpx2
import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.rag.qdrant import create_native_qdrant_client
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config.settings import AIConfig, load_settings
from devops_cli.telemetry.instruments import RAG_QUERY_DURATION, emit
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.qdrant import seed_scored_chunk

QUERY = "retry policy"


def _retriever(qdrant: Any, embedder: Any) -> SemanticRetriever:
    query_vector = embedder.embed_query(QUERY)
    seed_scored_chunk(
        qdrant, query_vector, 0.9, "def retry_policy(): return backoff", collection="code"
    )
    seed_scored_chunk(
        qdrant,
        query_vector,
        0.7,
        "The retry policy backs off between attempts.",
        collection="docs",
        file_path="docs/retry.md",
    )
    embedder.calls.clear()
    return SemanticRetriever(
        qdrant=qdrant, embedder=embedder, code_collection="code", docs_collection="docs"
    )


def _stage_points(otlp: FakeCollector) -> dict[tuple[str, str], float]:
    return {
        (attributes["stage"], attributes["outcome"]): value
        for attributes, value in otlp.points(RAG_QUERY_DURATION.name)
    }


def test_a_query_records_each_stage_and_the_whole_query(
    qdrant: Any, embedder: Any, otlp: FakeCollector
) -> None:
    results = _retriever(qdrant, embedder).search(QUERY)

    stages = _stage_points(otlp)
    assert (len(results) > 0, sorted(stages)) == (
        True,
        [("embedding", "ok"), ("ranking", "ok"), ("search", "ok"), ("total", "ok")],
    )
    parts = sum(stages[(stage, "ok")] for stage in ("embedding", "search", "ranking"))
    assert stages[("total", "ok")] >= parts


def test_a_stage_that_fails_is_observed_as_an_error(
    qdrant: Any, embedder: Any, otlp: FakeCollector
) -> None:
    """An embedding that fails still records its time, so the tail it causes is seen."""
    retriever = _retriever(qdrant, embedder)
    embedder.fail_next(EmbeddingsError("embedding timed out"))

    with pytest.raises(EmbeddingsError, match="embedding timed out"):
        retriever.search(QUERY)

    assert sorted(_stage_points(otlp)) == [("embedding", "error"), ("total", "error")]


def test_the_rag_histogram_tops_out_past_the_query_paths_timeouts(
    web: WebFake, otlp: FakeCollector
) -> None:
    """The top bucket is at least the longest request timeout a query waits on.

    A quantile past the top bucket reads as that bucket's bound, so a top bucket below the
    query's own timeouts drew its slow tail as a flat line (#975). The query embeds through the
    gateway with its default timeout and searches Qdrant with the default `qdrant.timeout`, read
    through the settings as every caller reads it. Sub-second buckets stay.
    """
    read_timeouts: list[float] = []

    def gateway_post(request: httpx2.Request) -> httpx2.Response:
        read_timeouts.append(float(request.extensions["timeout"]["read"] or 0))
        return httpx2.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    web.serve(gateway_post)
    gateway = AIConfig(provider="gateway", gateway_url="https://example.com/v1")
    EmbeddingsEngine(gateway, api_key="test-key", valkey_client=None).embed_query(QUERY)
    native = create_native_qdrant_client(
        "http://127.0.0.1:6333", timeout=load_settings().qdrant.timeout
    )
    longest_ms = 1000 * max([*read_timeouts, float(native._client._timeout)])

    emit(RAG_QUERY_DURATION, longest_ms, {"stage": "total", "outcome": "ok"})
    (histogram,) = (m for m in otlp.metrics if m["name"] == RAG_QUERY_DURATION.name)
    point = histogram["exponentialHistogram"]["dataPoints"][0]
    base = 2.0 ** (2.0 ** -int(point["scale"]))
    offset = int(point["positive"]["offset"])
    idx = next(i for i, c in enumerate(point["positive"]["bucketCounts"]) if int(c) > 0)
    low, high = base ** (offset + idx), base ** (offset + idx + 1)

    assert (
        len(read_timeouts),
        low < longest_ms <= high,
        (high - low) / longest_ms < 0.10,
    ) == (1, True, True)
