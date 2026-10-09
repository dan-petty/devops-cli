"""RAG query latency is timed by stage, and its histogram reaches past the query's timeouts (#975).

The RAG latency panel flattened at 5 s, the histogram's top bucket, though a query waits up to
30 s for the gateway's embedding and waited up to an hour for each Qdrant request, and nothing
split a query's time between embedding, the Qdrant searches and ranking. The code and docs
collections were also searched one after the other, and Qdrant retries went uncounted.
"""

from __future__ import annotations

import functools
import threading
import time
from types import SimpleNamespace
from typing import Any, cast

# qdrant_client sends its requests through httpx, not httpx2, so its transport errors are these.
import httpx
import httpx2
import pytest

from devops_cli.ai.rag import embeddings as embeddings_module
from devops_cli.ai.rag import qdrant as qdrant_module
from devops_cli.ai.rag import retriever as retriever_module
from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.rag.models import SearchResult
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.reranker import SearchReranker
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config.settings import AIConfig, load_settings
from devops_cli.telemetry import tracer as tracer_module
from devops_cli.telemetry.instruments import RAG_QUERY_DURATION, Instrument
from devops_cli.telemetry.tracer import OTelTelemetryClient, reset_tracer

Emitted = list[tuple[str, float, dict[str, Any] | None]]


@pytest.fixture(autouse=True)
def telemetry_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Export no spans or metrics, so no exporter thread starts while a query runs."""
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    reset_tracer()


class Clock:
    """A `perf_counter` the stubs move forward, so each stage takes a known time."""

    def __init__(self) -> None:
        self.now = 0.0
        self._lock = threading.Lock()

    def advance(self, seconds: float) -> None:
        with self._lock:
            self.now += seconds

    def perf_counter(self) -> float:
        return self.now


class StubEmbedder:
    """An embedder that answers every query with the same vector."""

    model = "stub-embedder"

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock

    def embed_query(self, text: str) -> list[float]:
        if self.clock:
            self.clock.advance(0.25)
        return [1.0, 0.0]


class StubQdrant:
    """A Qdrant client answering each collection with fixed points, after an optional hook."""

    def __init__(
        self,
        points: dict[str, list[dict[str, Any]]],
        before_reply: Any = None,
    ) -> None:
        self.points = points
        self.before_reply = before_reply

    def search_points(
        self,
        name: str,
        query_vector: list[float],
        *,
        limit: int,
        score_threshold: float | None,
        filter_payload: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if self.before_reply:
            self.before_reply(name)
        return [dict(point) for point in self.points[name]]


def _retriever(
    qdrant: StubQdrant | QdrantClient, embedder: StubEmbedder, **kwargs: Any
) -> SemanticRetriever:
    return SemanticRetriever(
        qdrant=cast(QdrantClient, qdrant),
        embedder=cast(EmbeddingsEngine, embedder),
        code_collection="code",
        docs_collection="docs",
        **kwargs,
    )


def _point(point_id: str, file_path: str, content: str, score: float) -> dict[str, Any]:
    return {
        "id": point_id,
        "score": score,
        "payload": {"file_path": file_path, "content": content, "language": "python"},
    }


def _recorder(emitted: Emitted) -> Any:
    def emit(
        instrument: Instrument, value: float, attributes: dict[str, Any] | None = None
    ) -> None:
        emitted.append((instrument.name, value, attributes))

    return emit


def _summary(results: list[SearchResult]) -> list[tuple[str, str, float, float | None]]:
    return [(r.chunk.id, r.chunk.file_path, r.score, r.rerank_score) for r in results]


CODE_POINTS = [
    _point("alpha", "src/alpha.py", "def retry_policy(): return backoff", 0.9),
    _point("shared", "src/shared.py", "class RetryPolicy: attempts = 3", 0.8),
]
DOCS_POINTS = [
    _point("shared", "docs/shared.md", "The retry policy backs off between attempts.", 0.7),
    _point("beta", "docs/beta.md", "Configure the retry policy in settings.", 0.6),
]


def test_a_query_records_each_stage_and_the_whole_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify one query observes embedding, Qdrant search, ranking and its whole time, by stage."""
    clock = Clock()
    emitted: Emitted = []
    monkeypatch.setattr(retriever_module, "time", clock)
    monkeypatch.setattr(retriever_module, "emit", _recorder(emitted))

    class TimedReranker(SearchReranker):
        def rerank(
            self, query: str, results: list[SearchResult], *, top_k: int | None = None
        ) -> list[SearchResult]:
            clock.advance(0.0625)
            return super().rerank(query, results, top_k=top_k)

    qdrant = StubQdrant(
        {"code": CODE_POINTS, "docs": DOCS_POINTS}, before_reply=lambda _: clock.advance(0.125)
    )
    retriever = _retriever(qdrant, StubEmbedder(clock), reranker=TimedReranker())

    results = retriever.search("retry policy")

    name = RAG_QUERY_DURATION.name
    assert (len(results) > 0, emitted) == (
        True,
        [
            (name, 250.0, {"stage": "embedding", "outcome": "ok"}),
            (name, 250.0, {"stage": "search", "outcome": "ok"}),
            (name, 62.5, {"stage": "ranking", "outcome": "ok"}),
            (name, 562.5, {"stage": "total", "outcome": "ok"}),
        ],
    )


def test_a_stage_that_fails_is_observed_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify an embedding that fails still records its time, so the tail it causes is seen."""
    clock = Clock()
    emitted: Emitted = []
    monkeypatch.setattr(retriever_module, "time", clock)
    monkeypatch.setattr(retriever_module, "emit", _recorder(emitted))

    class SlowFailingEmbedder(StubEmbedder):
        def embed_query(self, text: str) -> list[float]:
            clock.advance(15.0)
            raise EmbeddingsError("embedding timed out")

    qdrant = StubQdrant({"code": CODE_POINTS, "docs": DOCS_POINTS})
    retriever = _retriever(qdrant, SlowFailingEmbedder(clock))

    with pytest.raises(EmbeddingsError):
        retriever.search("retry policy")

    name = RAG_QUERY_DURATION.name
    assert emitted == [
        (name, 15000.0, {"stage": "embedding", "outcome": "error"}),
        (name, 15000.0, {"stage": "total", "outcome": "error"}),
    ]


def test_the_collections_are_searched_at_once_with_the_sequential_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the code and docs searches overlap and the result keeps the sequential order.

    The docs search answers first, yet the points are pooled code first, as the sequential
    search pooled them, so a point found in both collections keeps the same position, payload
    and fused score, and appears once. No search thread outlives the query.
    """
    monkeypatch.setattr(retriever_module, "emit", _recorder([]))
    docs_searching = threading.Event()
    overlapped: list[bool] = []

    def code_waits_for_docs(name: str) -> None:
        if name == "docs":
            docs_searching.set()
            return
        overlapped.append(docs_searching.wait(timeout=0.5))
        if not overlapped[-1]:
            raise TimeoutError("the docs search never started while the code search ran")

    sequential = _retriever(
        StubQdrant({"pooled": CODE_POINTS + DOCS_POINTS}), StubEmbedder()
    ).search("retry policy", collection="pooled")
    threads_before = set(threading.enumerate())
    concurrent = _retriever(
        StubQdrant({"code": CODE_POINTS, "docs": DOCS_POINTS}, before_reply=code_waits_for_docs),
        StubEmbedder(),
    ).search("retry policy")
    leaked = [t.name for t in threading.enumerate() if t not in threads_before]

    assert (
        overlapped,
        _summary(concurrent),
        sorted(r.chunk.id for r in concurrent),
        leaked,
    ) == (
        [True],
        _summary(sequential),
        ["alpha", "beta", "shared"],
        [],
    )


def test_each_collection_search_span_stays_under_the_query_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify both Qdrant search spans are the query span's children, the docs one from its thread.

    A thread starts with empty context variables, so a search span opened without the caller's
    context would start a trace of its own.
    """
    monkeypatch.setattr(retriever_module, "emit", _recorder([]))
    payloads: list[dict[str, Any]] = []
    client = OTelTelemetryClient(endpoint="http://127.0.0.1:9")
    monkeypatch.setattr(client, "_send_payload", lambda path, payload: payloads.append(payload))
    monkeypatch.setattr(tracer_module, "get_tracer", lambda: client)
    native = SimpleNamespace(query_points=lambda **kwargs: SimpleNamespace(points=[]))
    monkeypatch.setattr(qdrant_module, "NativeQdrantClient", lambda **kwargs: native)
    qdrant = QdrantClient("http://127.0.0.1:6333", api_key="test-key")

    _retriever(qdrant, StubEmbedder()).search("retry policy")

    spans = [
        span
        for payload in payloads
        for resource in payload.get("resourceSpans", [])
        for scope in resource["scopeSpans"]
        for span in scope["spans"]
    ]
    (query_span,) = [span for span in spans if span["name"] == "ai.rag.search"]
    assert [
        (span["traceId"], span.get("parentSpanId"))
        for span in spans
        if span["name"] == "ai.rag.qdrant_search"
    ] == [(query_span["traceId"], query_span["spanId"])] * 2


def test_a_query_waits_for_a_collection_search_that_ends_after_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the docs search, still running when the caller's code search returns, is pooled.

    The caller searches the code collection itself, so a docs search left unjoined would lose
    its points and outlive the query.
    """
    monkeypatch.setattr(retriever_module, "emit", _recorder([]))
    code_answered = threading.Event()

    def docs_answers_last(name: str) -> None:
        if name == "code":
            code_answered.set()
            return
        code_answered.wait(timeout=0.5)
        time.sleep(0.05)

    threads_before = set(threading.enumerate())
    results = _retriever(
        StubQdrant({"code": CODE_POINTS, "docs": DOCS_POINTS}, before_reply=docs_answers_last),
        StubEmbedder(),
    ).search("retry policy")
    leaked = [t.name for t in threading.enumerate() if t not in threads_before]

    assert (sorted(r.chunk.file_path for r in results), leaked) == (
        ["docs/beta.md", "docs/shared.md", "src/alpha.py"],
        [],
    )


def test_a_failed_collection_search_drops_only_that_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a collection whose search raises adds no points, as in the sequential search."""
    monkeypatch.setattr(retriever_module, "emit", _recorder([]))

    def docs_fails(name: str) -> None:
        if name == "docs":
            raise RuntimeError("docs collection unavailable")

    code_only = _retriever(StubQdrant({"code": CODE_POINTS}), StubEmbedder()).search(
        "retry policy", collection="code"
    )
    results = _retriever(
        StubQdrant({"code": CODE_POINTS, "docs": DOCS_POINTS}, before_reply=docs_fails),
        StubEmbedder(),
    ).search("retry policy")

    assert _summary(results) == _summary(code_only)


def test_an_interrupted_query_does_not_wait_for_the_other_searches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Ctrl-C during a query's own search raises at once, and leaves no thread to join.

    A pool's threads are joined when its `with` block exits and again when the interpreter
    exits, so an interrupted query waited out the other collection's search, up to three
    attempts of `qdrant.timeout` against a stalled Qdrant, and the process stayed alive until it
    ended (#975).
    """
    monkeypatch.setattr(retriever_module, "emit", _recorder([]))
    docs_searching, release, docs_done = threading.Event(), threading.Event(), threading.Event()
    docs_daemon: list[bool] = []

    def code_interrupted(name: str) -> None:
        if name == "docs":
            docs_daemon.append(threading.current_thread().daemon)
            docs_searching.set()
            release.wait(timeout=1.0)
            docs_done.set()
            return
        docs_searching.wait(timeout=1.0)
        raise KeyboardInterrupt

    retriever = _retriever(
        StubQdrant({"code": CODE_POINTS, "docs": DOCS_POINTS}, before_reply=code_interrupted),
        StubEmbedder(),
    )
    threads_before = set(threading.enumerate())

    with pytest.raises(KeyboardInterrupt):
        retriever.search("retry policy")
    docs_still_searching = not docs_done.is_set()
    release.set()
    for thread in set(threading.enumerate()) - threads_before:
        thread.join(timeout=1.0)

    assert (docs_still_searching, docs_daemon) == (True, [True])


def test_a_retried_qdrant_request_is_counted_by_the_error_behind_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify each retry counts once, by operation and the transport error qdrant_client wrapped.

    qdrant_client raises every transport error as a `ResponseHandlingException`, so labelling
    by that class gave a keep-alive connection the tunnel closed, retried within a second, the
    same `error_type` as a read that waited out its timeout (#975). The real client sends through
    an httpx transport that fails each way once, then answers.
    """
    emitted: Emitted = []
    monkeypatch.setattr(qdrant_module, "emit", _recorder(emitted))
    monkeypatch.setattr(qdrant_module, "time", SimpleNamespace(sleep=lambda _: None))
    failures: list[type[httpx.TransportError]] = [httpx.RemoteProtocolError, httpx.ReadTimeout]

    def qdrant_server(request: httpx.Request) -> httpx.Response:
        if failures:
            raise failures.pop(0)("transport failed", request=request)
        point = {"id": 7, "version": 0, "score": 0.9, "payload": {"file_path": "a.py"}}
        return httpx.Response(200, json={"result": {"points": [point]}, "status": "ok", "time": 0})

    from qdrant_client import QdrantClient as NativeQdrantClient

    monkeypatch.setattr(
        qdrant_module,
        "NativeQdrantClient",
        functools.partial(NativeQdrantClient, transport=httpx.MockTransport(qdrant_server)),
    )
    client = QdrantClient("https://127.0.0.1:6333", api_key="test-key")

    hits = client.search_points("code", [1.0, 0.0], limit=3)

    retries = "devops_cli_qdrant_retries_total"
    assert (hits, emitted) == (
        [{"id": 7, "score": 0.9, "payload": {"file_path": "a.py"}}],
        [
            (retries, 1, {"operation": "search_points", "error_type": "RemoteProtocolError"}),
            (retries, 1, {"operation": "search_points", "error_type": "ReadTimeout"}),
        ],
    )


def test_the_rag_histogram_tops_out_past_the_query_paths_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the top bucket is at least the longest request timeout a query waits on.

    A quantile past the top bucket reads as that bucket's bound, so a top bucket below the
    query's own timeouts drew its slow tail as a flat line (#975). The query embeds through the
    gateway with its default timeout and searches Qdrant with the default `qdrant.timeout`, read
    through the settings as every caller reads it. Qdrant's was an hour, and is now 300 s per
    attempt. Sub-second buckets stay.
    """
    read_timeouts: list[float] = []

    def gateway_post(self: httpx2.Client, url: str, **kwargs: Any) -> httpx2.Response:
        if url.endswith("/embeddings"):
            read_timeouts.append(float(self.timeout.read or 0))
        return httpx2.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    monkeypatch.setattr(embeddings_module, "validate_configured_service_url", lambda *a, **k: None)
    monkeypatch.setattr(httpx2.Client, "post", gateway_post)
    gateway = AIConfig(provider="gateway", gateway_url="https://example.com/v1")
    EmbeddingsEngine(gateway, api_key="test-key", valkey_client=None).embed_query("retry policy")

    native_timeouts: list[float] = []
    monkeypatch.setattr(
        qdrant_module,
        "NativeQdrantClient",
        lambda **kwargs: native_timeouts.append(float(kwargs["timeout"])),
    )
    configured = load_settings().qdrant.timeout
    QdrantClient("http://127.0.0.1:6333", api_key="test-key", timeout=configured)._get_client()

    longest_ms = 1000 * max(read_timeouts + native_timeouts)
    assert (
        len(read_timeouts + native_timeouts),
        min(longest_ms, RAG_QUERY_DURATION.bounds[-1]),
        RAG_QUERY_DURATION.bounds[:7],
    ) == (2, longest_ms, (10, 25, 50, 100, 250, 500, 1000))
