"""How RAG lookups pause after repeated transient failures, and how one probe resumes them."""

from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.ai.rag.investigator import investigate_rag_context
from devops_cli.config.settings import Settings
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.qdrant import seed_chunk
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until

pytestmark = pytest.mark.usefixtures("keyring_store")

LOOKUPS = 20


def _settings() -> Settings:
    settings = Settings()
    settings.ai.rag.enabled = True
    settings.qdrant.url = "http://192.0.2.10:6333"
    return settings


def _count_embeddings(embedder: Any) -> list[str]:
    """Record the text of each embedding request, before the fake answers or fails it."""
    requests: list[str] = []
    embedder.before_embed = lambda texts, is_query: requests.extend(texts)
    return requests


def _timeout(text: str) -> EmbeddingsError:
    return EmbeddingsError(f"Timeout embedding {text}", is_transient=True)


def _all_parked(threads: list[threading.Thread]) -> bool:
    """Whether every thread waits on a lock or an event, so none of them is about to send."""
    frames = sys._current_frames()
    return all(
        thread.ident in frames
        and frames[thread.ident].f_code.co_filename.endswith("threading.py")
        and frames[thread.ident].f_code.co_name in {"wait", "acquire"}
        for thread in threads
    )


def _run_concurrently(settings: Settings, queries: list[str]) -> list[Any]:
    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        futures = [executor.submit(investigate_rag_context, q, settings=settings) for q in queries]
        return [future.result() for future in futures]


def test_lookups_that_arrive_during_a_failing_probe_wait_and_then_skip(
    qdrant: Any, embedder: Any
) -> None:
    """One lookup probes; the 19 others wait for its outcome and send no request."""
    settings = _settings()
    requests: list[str] = []
    probe_started = threading.Event()
    release_probe = threading.Event()

    def hold_the_probe(texts: list[str], is_query: bool) -> None:
        requests.extend(texts)
        probe_started.set()
        release_probe.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    embedder.before_embed = hold_the_probe
    embedder.fail("Timeout hanging query", transient=True)
    results: list[Any] = []
    workers = [
        threading.Thread(
            target=lambda n=n: results.append(
                investigate_rag_context(f"query {n}", settings=settings)
            )
        )
        for n in range(LOOKUPS)
    ]
    workers[0].start()
    assert probe_started.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    for worker in workers[1:]:
        worker.start()
    # The probe holds in the embedder, and the others wait for it: all 20 threads are parked.
    assert wait_until(lambda: _all_parked(workers))
    release_probe.set()
    for worker in workers:
        worker.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert (len(requests), results) == (1, [None] * LOOKUPS)


def test_lookups_against_a_healthy_store_all_get_context(qdrant: Any, embedder: Any) -> None:
    seed_chunk(qdrant, embedder, "def hello(): pass")

    results = _run_concurrently(_settings(), ["def hello(): pass"] * LOOKUPS)

    assert [result is not None for result in results] == [True] * LOOKUPS


def test_three_timeouts_pause_lookups_for_60_seconds_and_a_probe_resumes_them(
    qdrant: Any, embedder: Any, clock: ClockFake
) -> None:
    seed_chunk(qdrant, embedder, "def hello(): pass")
    settings = _settings()
    requests = _count_embeddings(embedder)
    embedder.fail("Timeout embedding", transient=True)

    failed = [investigate_rag_context(f"query {n}", settings=settings) for n in (1, 2, 3)]
    clock.shift(15.0)
    paused_first = investigate_rag_context("query 4", settings=settings)
    clock.shift(15.0)
    paused_second = investigate_rag_context("query 5", settings=settings)
    sent_while_paused = len(requests)
    clock.shift(40.0)
    embedder.recover()
    probe = investigate_rag_context("def hello(): pass", settings=settings)
    resumed = investigate_rag_context("def hello(): pass again", settings=settings)

    assert (failed, paused_first, paused_second, sent_while_paused) == ([None] * 3, None, None, 3)
    assert (probe is not None, resumed is not None) == (True, True)


def test_a_rate_limited_lookup_pauses_nothing_for_the_run(qdrant: Any, embedder: Any) -> None:
    """A 429 counts as transient: the lookup is skipped, and the next one goes on."""
    seed_chunk(qdrant, embedder, "def hello(): pass")
    settings = _settings()
    embedder.fail_next(EmbeddingsError("429 No deployments available", is_transient=True))

    skipped = investigate_rag_context("def hello(): pass", settings=settings)
    served = investigate_rag_context("def hello(): pass again", settings=settings)

    assert (skipped, served is not None) == (None, True)


def test_a_failed_probe_pauses_lookups_for_60_seconds_more(
    qdrant: Any, embedder: Any, clock: ClockFake, caplog: pytest.LogCaptureFixture
) -> None:
    """The probe after a pause times out, so lookups pause again; the next probe resumes them.

    Each pause warns once, with the error of the failure that started it.
    """
    seed_chunk(qdrant, embedder, "def hello(): pass")
    settings = _settings()
    requests = _count_embeddings(embedder)
    embedder.fail_next(*(_timeout(text) for text in ("query 1", "query 2", "query 3", "probe 1")))

    with caplog.at_level(logging.WARNING, logger="devops_cli.ai.rag.investigator"):
        failures = [investigate_rag_context(f"query {n}", settings=settings) for n in (1, 2, 3)]
        clock.shift(60.0)
        failed_probe = investigate_rag_context("probe 1", settings=settings)
        clock.shift(59.0)
        in_the_second_pause = investigate_rag_context("query 4", settings=settings)
        clock.shift(1.0)
        probe = investigate_rag_context("probe 2", settings=settings)
        resumed = investigate_rag_context("query 5", settings=settings)

    assert (failures, failed_probe, in_the_second_pause) == ([None, None, None], None, None)
    assert (probe is not None, resumed is not None) == (True, True)
    assert requests == ["query 1", "query 2", "query 3", "probe 1", "probe 2", "query 5"]
    assert [record.getMessage() for record in caplog.records] == [
        "RAG lookups paused for 60s after 3 failures: Timeout embedding query 3.",
        "RAG lookups paused for 60s after 3 failures: Timeout embedding probe 1.",
    ]
