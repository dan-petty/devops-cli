"""A query searches the code and docs collections at once, and the result is the sequential one (#975)."""

from __future__ import annotations

import threading
from typing import Any

import pytest
from qdrant_client import QdrantClient as NativeQdrantClient

from devops_cli.ai.rag.models import SearchResult
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.retriever import SemanticRetriever
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.qdrant import seed_scored_chunk
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

pytestmark = pytest.mark.usefixtures("keyring_store")

QUERY = "retry policy"
CODE = [
    ("alpha", "src/alpha.py", "def retry_policy(): return backoff", 0.9),
    ("shared", "src/shared.py", "class RetryPolicy: attempts = 3", 0.8),
]
DOCS = [
    ("gamma", "docs/gamma.md", "The retry policy backs off between attempts.", 0.7),
    ("beta", "docs/beta.md", "Configure the retry policy in settings.", 0.6),
]


def _seed(qdrant: Any, embedder: Any, collections: dict[str, list[tuple[str, str, str, float]]]):
    vector = embedder.embed_query(QUERY)
    for collection, chunks in collections.items():
        for point_id, file_path, content, score in chunks:
            seed_scored_chunk(
                qdrant,
                vector,
                score,
                content,
                collection=collection,
                file_path=file_path,
                point_id=point_id,
            )


def _retriever(qdrant: Any, embedder: Any) -> SemanticRetriever:
    return SemanticRetriever(
        qdrant=qdrant, embedder=embedder, code_collection="code", docs_collection="docs"
    )


def _summary(results: list[SearchResult]) -> list[tuple[str, str, float, float | None]]:
    return [(r.chunk.id, r.chunk.file_path, r.score, r.rerank_score) for r in results]


def _search_threads() -> set[threading.Thread]:
    return set(threading.enumerate())


def test_the_collections_are_searched_at_once_with_the_sequential_result(
    qdrant: Any, embedder: Any
) -> None:
    """The code and docs searches overlap, and the result keeps the sequential order.

    The docs search answers first, yet the points are pooled code first, as the sequential
    search pooled them. No search thread outlives the query.
    """
    _seed(qdrant, embedder, {"code": CODE, "docs": DOCS, "pooled": CODE + DOCS})
    sequential = _retriever(qdrant, embedder).search(QUERY, collection="pooled")
    docs_searching = threading.Event()
    overlapped: list[bool] = []

    def code_waits_for_docs(name: str) -> None:
        if name == "docs":
            docs_searching.set()
        elif name == "code":
            overlapped.append(docs_searching.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))

    qdrant.on_search = code_waits_for_docs
    threads_before = _search_threads()
    concurrent = _retriever(qdrant, embedder).search(QUERY)
    leaked = [t.name for t in threading.enumerate() if t not in threads_before]

    assert (overlapped, _summary(concurrent), leaked) == ([True], _summary(sequential), [])


def test_a_query_waits_for_a_collection_search_that_ends_after_its_own(
    qdrant: Any, embedder: Any
) -> None:
    """The docs search, still running when the caller's code search returns, is pooled.

    The caller searches the code collection itself, so a docs search left unjoined would lose
    its points and outlive the query.
    """
    _seed(qdrant, embedder, {"code": CODE, "docs": DOCS})
    code_answered = threading.Event()
    docs_after_code: list[bool] = []

    def docs_answers_last(name: str) -> None:
        if name == "code":
            code_answered.set()
        elif name == "docs":
            docs_after_code.append(code_answered.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))

    qdrant.on_search = docs_answers_last
    threads_before = _search_threads()
    results = _retriever(qdrant, embedder).search(QUERY)
    leaked = [t.name for t in threading.enumerate() if t not in threads_before]

    assert (sorted(r.chunk.file_path for r in results), leaked, docs_after_code) == (
        ["docs/beta.md", "docs/gamma.md", "src/alpha.py", "src/shared.py"],
        [],
        [True],
    )


def test_a_failed_collection_search_drops_only_that_collection(qdrant: Any, embedder: Any) -> None:
    _seed(qdrant, embedder, {"code": CODE, "docs": DOCS})
    code_only = _retriever(qdrant, embedder).search(QUERY, collection="code")

    def docs_fails(name: str) -> None:
        if name == "docs":
            raise RuntimeError("docs collection unavailable")

    qdrant.on_search = docs_fails
    results = _retriever(qdrant, embedder).search(QUERY)

    assert _summary(results) == _summary(code_only)


def test_an_interrupted_query_does_not_wait_for_the_other_searches(
    qdrant: Any, embedder: Any
) -> None:
    """Ctrl-C during a query's own search raises at once, and leaves no thread to join.

    A pool's threads are joined when its `with` block exits and again when the interpreter
    exits, so an interrupted query waited out the other collection's search, up to three
    attempts of `qdrant.timeout` against a stalled Qdrant, and the process stayed alive until it
    ended (#975).
    """
    _seed(qdrant, embedder, {"code": CODE, "docs": DOCS})
    docs_searching, release, docs_done = threading.Event(), threading.Event(), threading.Event()
    docs_daemon: list[bool] = []
    handoffs: dict[str, bool] = {}

    def code_interrupted(name: str) -> None:
        if name == "docs":
            docs_daemon.append(threading.current_thread().daemon)
            docs_searching.set()
            # The docs search is held until the test releases it, which it records.
            handoffs["docs released"] = release.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
            docs_done.set()
        elif name == "code":
            handoffs["docs started"] = docs_searching.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
            raise KeyboardInterrupt

    qdrant.on_search = code_interrupted
    retriever = _retriever(qdrant, embedder)
    threads_before = _search_threads()

    with pytest.raises(KeyboardInterrupt) as raised:
        retriever.search(QUERY)
    assert raised.value is not None
    docs_still_searching = not docs_done.is_set()
    release.set()
    for thread in set(threading.enumerate()) - threads_before:
        thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert (docs_still_searching, docs_daemon, handoffs) == (
        True,
        [True],
        {"docs started": True, "docs released": True},
    )


@pytest.mark.filterwarnings("ignore:Payload indexes have no effect in the local Qdrant")
def test_each_collection_search_span_stays_under_the_query_span(
    embedder: Any, otlp: FakeCollector
) -> None:
    """Both Qdrant search spans are the query span's children, the docs one from its thread.

    A thread starts with empty context variables, so a search span opened without the caller's
    context would start a trace of its own. The client is the real one, over the native
    client's in-memory mode.
    """
    qdrant = QdrantClient(
        "http://127.0.0.1:6333",
        client=NativeQdrantClient(location=":memory:"),
        api_key="test-key",
        timeout=5.0,
    )
    for collection in ("code", "docs"):
        qdrant.ensure_collection(collection, len(embedder.embed_query(QUERY)))

    _retriever(qdrant, embedder).search(QUERY)

    spans = otlp.spans
    (query_span,) = [span for span in spans if span.name == "ai.rag.search"]
    assert [
        (span.trace_id, span.parent_span_id)
        for span in spans
        if span.name == "ai.rag.qdrant_search"
    ] == [(query_span.trace_id, query_span.span_id)] * 2
