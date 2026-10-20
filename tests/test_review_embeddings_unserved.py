"""Persona review against a gateway that serves no embedding model (reported 2026-10-02)."""

from __future__ import annotations

import logging
import socket
import threading
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import urlsplit

import httpx2
import pytest

from devops_cli.ai.rag import investigator
from devops_cli.ai.rag.models import RAGContext
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.review.pipeline import _resolve_rag_and_contract_context
from devops_cli.ai.review.pool import ReviewWorkerPool
from devops_cli.ai.review_schema import FileReviewPayload
from devops_cli.config import settings as settings_mod
from devops_cli.config.settings import AITaskOverride, Settings
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

GATEWAY = "https://example.com/v1"
QDRANT_URL = "https://example.com:6333"
WORKERS = 4


@pytest.fixture
def embedding_posts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """A gateway whose backends serve only the review model: every embedding request fails."""
    posts: list[str] = []

    def refuse(self: httpx2.Client, url: Any, **kwargs: Any) -> httpx2.Response:
        posts.append(str(url))
        return httpx2.Response(
            400,
            json={"error": {"message": "model 'bge-m3:latest' is not loaded on any backend"}},
            request=httpx2.Request("POST", str(url)),
        )

    st = Settings()
    st.ai.provider = "gateway"
    st.ai.gateway_url = GATEWAY
    st.ai.tasks.embedding = AITaskOverride(
        provider="gateway", model="bge-m3:latest", api_base_url=GATEWAY
    )
    st.ai.rag.enabled = True
    st.qdrant.url = QDRANT_URL
    monkeypatch.setattr(settings_mod, "load_settings", lambda *a, **k: st)
    monkeypatch.setattr(settings_mod, "get_ai_api_key", lambda *a, **k: "test-key")
    monkeypatch.setattr(settings_mod, "get_qdrant_api_key", lambda *a, **k: None)
    monkeypatch.setattr("devops_cli.core.validation.validate_url", lambda url, *a, **k: url)
    # A Qdrant whose collections hold one point embedded with the configured model: every call a
    # lookup makes is answered here, so none reaches the network.
    payload = {
        "file_path": "src/x.py",
        "content": "def x(): ...",
        "embedding_model": "bge-m3:latest",
    }
    hit = {"id": 1, "score": 0.9, "payload": payload}
    point = {"id": 1, "payload": payload, "vector": None}
    info = {"status": "green", "points_count": 1, "vectors_count": 1, "vector_size": 3}
    monkeypatch.setattr(QdrantClient, "is_alive", lambda self, **k: True)
    monkeypatch.setattr(QdrantClient, "get_collection_info", lambda self, *a, **k: info)
    monkeypatch.setattr(QdrantClient, "scroll_points", lambda self, *a, **k: [point])
    monkeypatch.setattr(QdrantClient, "search_points", lambda self, *a, **k: [hit])
    monkeypatch.setattr(httpx2.Client, "post", refuse)
    investigator.clear_investigation_cache()
    yield posts
    investigator.clear_investigation_cache()


def _serving(posts: list[str]) -> Callable[..., httpx2.Response]:
    """A gateway whose backends serve the embedding model: every request gets a vector for each
    of its inputs."""

    def answer(self: httpx2.Client, url: Any, **kwargs: Any) -> httpx2.Response:
        posts.append(str(url))
        texts = kwargs["json"]["input"]
        data = [{"index": i, "embedding": [0.1, 0.2, 0.3]} for i in range(len(texts))]
        return httpx2.Response(200, json={"data": data}, request=httpx2.Request("POST", str(url)))

    return answer


def _is_embedding_request(url: str) -> bool:
    return url.endswith("/embeddings")


def _embedding_requests(posts: list[str]) -> list[str]:
    return [url for url in posts if _is_embedding_request(url)]


def _resolve_file_context(index: int) -> tuple[str, str]:
    """One review worker's per-file payload lookup, as stage 3 runs it, without contracts."""
    path = f"src/mod{index}.py"
    return _resolve_rag_and_contract_context(
        path, ".py", f"symbol{index}", "", FileReviewPayload(file_path=path), False
    )


def _resolve_files(n: int, start: int = 0) -> list[tuple[str, str]]:
    """The per-file lookups of `n` files, one after another."""
    return [_resolve_file_context(index) for index in range(start, start + n)]


def _hold_replies_until_lookups_start(
    monkeypatch: pytest.MonkeyPatch, lookups: int
) -> tuple[list[str], list[bool]]:
    """Hold each gateway reply until `lookups` RAG lookups have started. Their queries, and for
    each held reply whether the lookups starting let it go rather than the bound running out."""
    started: list[str] = []
    released: list[bool] = []
    all_started = threading.Event()
    lock = threading.Lock()
    lookup = investigator.investigate_rag_context
    reply = httpx2.Client.post

    def counted(query: str, **kwargs: Any) -> RAGContext | None:
        with lock:
            started.append(query)
            if len(started) == lookups:
                all_started.set()
        return lookup(query, **kwargs)

    def held(self: httpx2.Client, url: Any, **kwargs: Any) -> httpx2.Response:
        released.append(all_started.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS))
        return reply(self, url, **kwargs)

    monkeypatch.setattr(investigator, "investigate_rag_context", counted)
    monkeypatch.setattr(httpx2.Client, "post", held)
    return started, released


def test_a_review_asks_for_an_unserved_embedding_model_once(
    embedding_posts: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    """Five files' lookups make at most one embedding request, and no context comes from a
    fallback.

    The run-wide stop logs exactly one warning, naming the model, the gateway's answer and how
    to fix it.
    """
    with caplog.at_level(logging.WARNING):
        contexts = _resolve_files(5)

    embeds = [url for url in embedding_posts if url.endswith("/embeddings")]
    assert (len(embeds) <= 1, contexts) == (True, [("", "")] * 5)
    warnings = [
        (record.name, record.levelname, record.getMessage())
        for record in caplog.records
        if record.levelno >= logging.WARNING and record.name.startswith("devops_cli")
    ]
    names = (
        "bge-m3:latest",
        f"{GATEWAY}/embeddings answered HTTP 400",
        "is not loaded on any backend",
        "ai.tasks.embedding",
        "ai.rag.enabled: false",
    )
    assert [
        (logger, level, all(name in message for name in names))
        for logger, level, message in warnings
    ] == [("devops_cli.ai.rag.investigator", "WARNING", True)]


def test_after_the_stop_a_second_batch_sends_no_request(
    embedding_posts: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once RAG stops, later files neither build a retriever nor ask for an embedding.

    The first batch sends exactly one request, the one that stops RAG.
    """
    _resolve_files(5)
    sent = len(_embedding_requests(embedding_posts))
    built: list[tuple[Any, ...]] = []
    build = investigator._get_or_create_retriever
    monkeypatch.setattr(
        investigator, "_get_or_create_retriever", lambda *a: built.append(a) or build(*a)
    )

    contexts = _resolve_files(5, start=5)

    assert (sent, len(_embedding_requests(embedding_posts)) - sent, built, contexts) == (
        1,
        0,
        [],
        [("", "")] * 5,
    )


def test_parallel_review_workers_ask_an_unserved_embedding_model_once(
    embedding_posts: list[str], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Workers that look up their files' context together send one request between them.

    The gateway holds its reply until every worker has started its lookup, so no worker can
    learn of the stop from a reply that came back before it began.
    """
    started, released = _hold_replies_until_lookups_start(monkeypatch, WORKERS)

    with caplog.at_level(logging.WARNING):
        contexts = ReviewWorkerPool.create(concurrency=WORKERS).run_sync_all(
            _resolve_file_context, range(WORKERS), return_exceptions=True
        )

    warnings = [
        (record.name, record.levelname)
        for record in caplog.records
        if record.levelno >= logging.WARNING and record.name.startswith("devops_cli")
    ]
    assert (
        len(started),
        bool(released) and all(released),
        len(_embedding_requests(embedding_posts)),
        contexts,
        warnings,
    ) == (
        WORKERS,
        True,
        1,
        [("", "")] * WORKERS,
        [("devops_cli.ai.rag.investigator", "WARNING")],
    )


def test_once_the_model_answers_lookups_stop_taking_turns(
    embedding_posts: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lookups take turns only until the model first answers, so a served model is not slowed.

    After one lookup has embedded its query, the gateway holds each reply until every worker's
    request has arrived. That happens only when the workers' requests are in flight together.
    """

    answer = _serving(embedding_posts)
    together = threading.Barrier(WORKERS, timeout=THREAD_HANDOFF_BOUND_SECONDS)

    def held(self: httpx2.Client, url: Any, **kwargs: Any) -> httpx2.Response:
        # Only the workers' embedding requests meet at the barrier. The tracer's exporter
        # threads post through this same patched method, and a trace export that took a
        # worker's place left that worker's request waiting at the barrier until it broke.
        if _is_embedding_request(str(url)):
            together.wait()
        return answer(self, url, **kwargs)

    monkeypatch.setattr(httpx2.Client, "post", answer)
    first = _resolve_file_context(WORKERS)
    monkeypatch.setattr(httpx2.Client, "post", held)
    contexts = ReviewWorkerPool.create(concurrency=WORKERS).run_sync_all(
        _resolve_file_context, range(WORKERS), return_exceptions=True
    )

    assert (
        bool(first[0]),
        len(_embedding_requests(embedding_posts)),
        [isinstance(context, tuple) and bool(context[0]) for context in contexts],
        together.broken,
    ) == (True, WORKERS + 1, [True] * WORKERS, False)


def test_clearing_the_investigation_cache_lifts_the_stop(embedding_posts: list[str]) -> None:
    """`clear_investigation_cache()` turns RAG back on, so the next lookup asks again."""
    _resolve_files(1)
    investigator.clear_investigation_cache()
    _resolve_files(1, start=1)

    assert len(_embedding_requests(embedding_posts)) == 2


def test_a_served_lookup_looks_up_no_service_host(
    embedding_posts: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fixture's Qdrant answers every call a lookup makes, so a lookup reaches no network.

    Its collection-info read went to the real client, which looked up the Qdrant host (refused by
    the suite's guard) and slept through about 3 s of retries.
    """
    looked_up: list[str] = []
    resolve = socket.getaddrinfo

    def recording(host: Any, *args: Any, **kwargs: Any) -> Any:
        looked_up.append(str(host))
        return resolve(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", recording)
    monkeypatch.setattr(httpx2.Client, "post", _serving(embedding_posts))
    context = _resolve_file_context(0)

    service_hosts = {urlsplit(GATEWAY).hostname, urlsplit(QDRANT_URL).hostname}
    assert (bool(context[0]), [host for host in looked_up if host in service_hosts]) == (True, [])
