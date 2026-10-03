"""Verification against a gateway that serves no embedding model (reported 2026-10-02)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from typing import Any

import httpx2
import pytest

from devops_cli.ai.rag import investigator
from devops_cli.ai.rag.models import RAGContext
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.review.pipeline import _resolve_rag_and_contract_context
from devops_cli.ai.review.pool import ReviewWorkerPool
from devops_cli.ai.review.verification import _collect_rag_verification_blocks
from devops_cli.ai.review_schema import FileReviewPayload, Finding
from devops_cli.config import settings as settings_mod
from devops_cli.config.settings import AITaskOverride, Settings

GATEWAY = "https://example.com/v1"
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
    st.qdrant.url = "https://example.com:6333"
    monkeypatch.setattr(settings_mod, "load_settings", lambda *a, **k: st)
    monkeypatch.setattr(settings_mod, "get_ai_api_key", lambda *a, **k: "test-key")
    monkeypatch.setattr(settings_mod, "get_qdrant_api_key", lambda *a, **k: None)
    monkeypatch.setattr("devops_cli.core.validation.validate_url", lambda url, *a, **k: url)
    monkeypatch.setattr(QdrantClient, "is_alive", lambda self, **k: True)
    hit = {"id": 1, "score": 0.9, "payload": {"file_path": "src/x.py", "content": "def x(): ..."}}
    monkeypatch.setattr(QdrantClient, "search_points", lambda self, *a, **k: [hit])
    monkeypatch.setattr(httpx2.Client, "post", refuse)
    investigator.clear_investigation_cache()
    yield posts
    investigator.clear_investigation_cache()


def _findings(n: int, start: int = 0) -> list[Finding]:
    return [
        Finding(
            severity="HIGH",
            location=f"src/mod{i}.py:1",
            title=f"Finding {i}",
            description=f"Description of finding {i}",
            fix="none",
        )
        for i in range(start, start + n)
    ]


def _embedding_requests(posts: list[str]) -> list[str]:
    return [url for url in posts if url.endswith("/embeddings")]


def _resolve_file_context(index: int) -> tuple[str, str]:
    """One review worker's per-file payload lookup, as stage 3 runs it, without contracts."""
    path = f"src/mod{index}.py"
    return _resolve_rag_and_contract_context(
        path, ".py", f"symbol{index}", "", FileReviewPayload(file_path=path), False
    )


def _hold_replies_until_lookups_start(monkeypatch: pytest.MonkeyPatch, lookups: int) -> list[str]:
    """Hold each gateway reply until `lookups` RAG lookups have started; their queries."""
    started: list[str] = []
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
        all_started.wait(timeout=2.0)
        return reply(self, url, **kwargs)

    monkeypatch.setattr(investigator, "investigate_rag_context", counted)
    monkeypatch.setattr(httpx2.Client, "post", held)
    return started


def test_verification_asks_for_an_unserved_embedding_model_once(
    embedding_posts: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    """Five findings make at most one embedding request, and no context comes from a fallback.

    The run-wide stop logs exactly one warning, naming the model, the gateway's answer and how
    to fix it.
    """
    with caplog.at_level(logging.WARNING):
        blocks = _collect_rag_verification_blocks(_findings(5))

    embeds = [url for url in embedding_posts if url.endswith("/embeddings")]
    assert (len(embeds) <= 1, blocks) == (True, [])
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
    """Once RAG stops, later findings neither build a retriever nor ask for an embedding.

    The first batch sends exactly one request, the one that stops RAG.
    """
    _collect_rag_verification_blocks(_findings(5))
    sent = len(_embedding_requests(embedding_posts))
    built: list[tuple[Any, ...]] = []
    build = investigator._get_or_create_retriever
    monkeypatch.setattr(
        investigator, "_get_or_create_retriever", lambda *a: built.append(a) or build(*a)
    )

    blocks = _collect_rag_verification_blocks(_findings(5, start=5))

    assert (sent, len(_embedding_requests(embedding_posts)) - sent, built, blocks) == (
        1,
        0,
        [],
        [],
    )


def test_parallel_review_workers_ask_an_unserved_embedding_model_once(
    embedding_posts: list[str], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Workers that look up their files' context together send one request between them.

    The gateway holds its reply until every worker has started its lookup, so no worker can
    learn of the stop from a reply that came back before it began.
    """
    started = _hold_replies_until_lookups_start(monkeypatch, WORKERS)

    with caplog.at_level(logging.WARNING):
        contexts = ReviewWorkerPool.create(concurrency=WORKERS).run_sync_all(
            _resolve_file_context, range(WORKERS), return_exceptions=True
        )

    warnings = [
        (record.name, record.levelname)
        for record in caplog.records
        if record.levelno >= logging.WARNING and record.name.startswith("devops_cli")
    ]
    assert (len(started), len(_embedding_requests(embedding_posts)), contexts, warnings) == (
        WORKERS,
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

    def answer(self: httpx2.Client, url: Any, **kwargs: Any) -> httpx2.Response:
        embedding_posts.append(str(url))
        texts = kwargs["json"]["input"]
        data = [{"index": i, "embedding": [0.1, 0.2, 0.3]} for i in range(len(texts))]
        return httpx2.Response(200, json={"data": data}, request=httpx2.Request("POST", str(url)))

    together = threading.Barrier(WORKERS, timeout=2.0)

    def held(self: httpx2.Client, url: Any, **kwargs: Any) -> httpx2.Response:
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
    _collect_rag_verification_blocks(_findings(1))
    investigator.clear_investigation_cache()
    _collect_rag_verification_blocks(_findings(1, start=1))

    assert len(_embedding_requests(embedding_posts)) == 2
