"""How an engine fails over between nodes, cuts a slow batch, and sizes its batches (#2011, #2072)."""

from __future__ import annotations

import threading
from collections.abc import Callable

import httpcore2
import httpx2
import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.config import defaults
from tests.support.embedding_replies import (
    SERVING_BACKEND,
    gateway_config,
    gateway_engine,
    gateway_reply,
    inputs,
    ollama_config,
    ollama_engine,
    ollama_reply,
    serve,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.gateway_dial import (
    REPLY_WIDTH,
    dial_gateway,
    reply_bytes,
    wait_for,
)
from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def _timeout_on_port(port: int) -> Callable[[httpx2.Request], httpx2.Response]:
    """A node reply that times out on the node at `port` and answers on any other."""

    def reply(request: httpx2.Request) -> httpx2.Response:
        if request.url.port == port:
            raise httpx2.ReadTimeout("Simulated read timeout", request=request)
        return ollama_reply(request)

    return reply


def test_a_node_that_times_out_fails_over_to_the_next_one(clock: ClockFake, web: WebFake) -> None:
    sent = serve(web, _timeout_on_port(11434))
    engine = ollama_engine(["http://example.com:11434", "http://example.com:11435"])

    vectors = engine.embed_texts(["test chunk"])

    assert (vectors, [request.url.port for request in sent], len(clock.waits)) == (
        [[0.5] * 4],
        [11434, 11435],
        1,
    )


def test_each_node_that_times_out_waits_longer_before_the_next_one(
    clock: ClockFake, web: WebFake
) -> None:
    """The wait doubles with each node, up to a cap, with up to a tenth of jitter."""
    serve(web, lambda request: (_ for _ in ()).throw(httpx2.ReadTimeout("slow", request=request)))
    engine = ollama_engine([f"http://example.com:{11434 + n}" for n in range(3)])

    with pytest.raises(EmbeddingsError, match="ReadTimeout"):
        engine.embed_texts(["test chunk"])

    first, second, third = clock.waits
    assert (0.5 <= first <= 0.55, 1.0 <= second <= 1.1, 2.0 <= third <= 2.2) == (True, True, True)


def test_the_wait_between_nodes_stops_growing_at_the_cap(clock: ClockFake, web: WebFake) -> None:
    """With more nodes than doublings to the cap, no wait is longer than the cap and its jitter."""
    serve(web, lambda request: (_ for _ in ()).throw(httpx2.ReadTimeout("slow", request=request)))
    engine = ollama_engine([f"http://example.com:{11434 + n}" for n in range(6)])

    with pytest.raises(EmbeddingsError, match="ReadTimeout"):
        engine.embed_texts(["test chunk"])

    cap = defaults.DEFAULT_RAG_EMBEDDING_MAX_BACKOFF_SECONDS
    assert (len(clock.waits), max(clock.waits) <= cap * 1.1) == (6, True)


def test_a_batch_that_times_out_is_cut_into_smaller_ones(clock: ClockFake, web: WebFake) -> None:
    def reply(request: httpx2.Request) -> httpx2.Response:
        if len(inputs(request)) >= 4:
            raise httpx2.ReadTimeout("Timeout on large batch of 4", request=request)
        return ollama_reply(request)

    sent = serve(web, reply)
    engine = ollama_engine([SERVING_BACKEND], batch_size=4)

    vectors = engine.embed_texts(["chunk_1", "chunk_2", "chunk_3", "chunk_4"])

    assert (vectors, [len(inputs(request)) for request in sent]) == ([[0.5] * 4] * 4, [4, 2, 2])


_SLOWEST_MEASURED_BATCH_SECONDS = 76.0


@pytest.mark.usefixtures("clock")
def test_a_batch_that_times_out_leaves_the_parallel_batches_their_connections(
    monkeypatch: pytest.MonkeyPatch,
    dns: DnsFake,
) -> None:
    """A batch that times out does not close the connections of the batches parallel to it.

    Four batches of one text go out in parallel. The gateway keeps the first batch without a
    reply until all four batches are sent, and then the read of that batch times out. The gateway
    replies to the other three batches only after the engine sends the first batch again. Each of
    the three batches reads its reply on its own connection. Thus the gateway gets five requests,
    and no reply comes to a closed connection.
    """
    names = [f"batch {index}" for index in range(4)]
    every_batch_sent = threading.Event()
    first_batch_sent_again = threading.Event()

    def answer(texts: list[str], _read_timeout: float | None) -> bytes:
        name, sent = texts[0], gateway.sent()
        if set(sent) == set(names):
            every_batch_sent.set()
        if name == names[0] and sent.count(name) == 1:
            wait_for(every_batch_sent, "the first request of each batch")
            raise httpcore2.ReadTimeout("timed out")
        if name == names[0]:
            first_batch_sent_again.set()
        elif sent.count(name) == 1:
            wait_for(first_batch_sent_again, "the second request of the first batch")
        return reply_bytes(texts, value=float(names.index(name)))

    gateway = dial_gateway(monkeypatch, dns, answer)

    vectors = gateway_engine(batch_size=1).embed_texts(names)

    assert (vectors, sorted(gateway.sent()), gateway.closed_before_reply) == (
        [[float(index)] * REPLY_WIDTH for index in range(len(names))],
        [names[0], *names],
        [],
    )


@pytest.mark.usefixtures("clock")
def test_the_largest_intake_batch_gets_a_reply_as_slow_as_the_slowest_measured(
    monkeypatch: pytest.MonkeyPatch,
    dns: DnsFake,
) -> None:
    """The read timeout of a gateway batch is longer than the slowest reply measured for a batch.

    Intake sends batches of up to `DEFAULT_RAG_EMBEDDING_BATCH_SIZE` texts, and it cuts each text
    to `DEFAULT_ROADMAP_INTAKE_TEXT_CHARS` characters. The gateway replies to a batch of that size
    after 76 s, as the slowest tier did on 2026-10-23, so a request with a shorter read timeout
    times out. The batch gets its reply to its first request, which waits the named default.
    """

    def answer(texts: list[str], read_timeout: float | None) -> bytes:
        if read_timeout is not None and read_timeout < _SLOWEST_MEASURED_BATCH_SECONDS:
            raise httpcore2.ReadTimeout("timed out")
        return reply_bytes(texts)

    gateway = dial_gateway(monkeypatch, dns, answer)
    texts = [
        f"item {index} ".ljust(defaults.DEFAULT_ROADMAP_INTAKE_TEXT_CHARS, "x")
        for index in range(defaults.DEFAULT_RAG_EMBEDDING_BATCH_SIZE)
    ]

    vectors = gateway_engine().embed_texts(texts)

    assert (len(vectors), gateway.requests, gateway.read_timeouts) == (
        defaults.DEFAULT_RAG_EMBEDDING_BATCH_SIZE,
        [texts],
        [defaults.DEFAULT_RAG_EMBEDDING_BATCH_TIMEOUT],
    )


def test_a_configured_embedding_timeout_is_the_read_timeout_of_a_gateway_batch(
    monkeypatch: pytest.MonkeyPatch,
    dns: DnsFake,
) -> None:
    """`ai.tasks.embedding.timeout` sets the read timeout of a gateway batch, also below 30 s."""
    gateway = dial_gateway(monkeypatch, dns, lambda texts, _read_timeout: reply_bytes(texts))
    ai_cfg = gateway_config()
    ai_cfg.tasks.embedding.timeout = 10.0

    gateway_engine(ai_cfg).embed_texts(["one text"])

    assert gateway.read_timeouts == [10.0]


_SLOW_BATCH_SECONDS = defaults.DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS + 1.0


class _TimedNode:
    """The replies of one Ollama node, each taking the next of `seconds` on the fake clock.

    The last of `seconds` repeats for every later reply. A test sets `seconds` again between calls.
    """

    def __init__(self, clock: ClockFake, *seconds: float) -> None:
        self.clock = clock
        self.seconds = list(seconds)

    def reply(self, request: httpx2.Request) -> httpx2.Response:
        taken = self.seconds.pop(0) if len(self.seconds) > 1 else self.seconds[0]
        self.clock.shift(taken)
        return ollama_reply(request)


def _batch_sizes(
    engine: EmbeddingsEngine, sent: list[httpx2.Request], call: int, texts: int
) -> list[int]:
    """Embed `texts` new texts in one call, and give the size of each batch it sent, largest first."""
    sent.clear()
    engine.embed_texts([f"call {call} text {index}" for index in range(texts)])
    return sorted((len(inputs(request)) for request in sent), reverse=True)


def test_parallel_slow_batches_halve_the_batch_size_once_for_the_size_they_were_sent_at(
    clock: ClockFake, web: WebFake
) -> None:
    """A slow batch halves the batch size only when it holds no more texts than the size in use.

    Each call cuts eight texts at the size in use, and two workers send the batches in parallel.
    Each reply takes longer than the latency threshold. The first slow batch of a call halves the
    size. The other batches of that call hold more texts than the halved size, so they do not
    halve it again. At one text, the size stays at one text.
    """
    sent = serve(web, _TimedNode(clock, _SLOW_BATCH_SECONDS).reply)
    engine = EmbeddingsEngine(ollama_config(), valkey_client=None, batch_size=4)

    sizes = [_batch_sizes(engine, sent, call, 8) for call in range(4)]

    assert sizes == [[4, 4], [2, 2, 2, 2], [1] * 8, [1] * 8]


def test_parallel_batches_that_time_out_on_an_ollama_node_halve_the_batch_size_once(
    clock: ClockFake, web: WebFake
) -> None:
    """Two batches of four texts time out in parallel on the one node, and the size halves once.

    The two batches wait their backoff at the same time, so both timeouts come before a reply.
    Then the engine sends each batch again as two halves, and the node replies at once. These
    replies come in the cooldown, so the size stays at two texts for the next call.
    """

    def reply(request: httpx2.Request) -> httpx2.Response:
        texts = inputs(request)
        if len(texts) == 4 and texts[0].startswith("call 0 "):
            raise httpx2.ReadTimeout("timed out", request=request)
        return ollama_reply(request)

    sent = serve(web, reply)
    engine = EmbeddingsEngine(ollama_config(), valkey_client=None, batch_size=4)

    with clock.concurrent_sleeps(2):
        first_call = _batch_sizes(engine, sent, 0, 8)
    second_call = _batch_sizes(engine, sent, 1, 8)

    assert [first_call, second_call] == [[4, 4, 2, 2, 2, 2], [2, 2, 2, 2]]


def test_parallel_gateway_batches_that_time_out_halve_the_batch_size_once(
    clock: ClockFake, web: WebFake
) -> None:
    """Two gateway batches of four texts time out in parallel, and the size halves once.

    The first request of each batch times out, the two batches wait their backoff at the same
    time, and the second request of each batch gets its reply. The next call cuts its texts into
    batches of two texts.
    """
    timed_out: set[str] = set()
    lock = threading.Lock()

    def reply(request: httpx2.Request) -> httpx2.Response:
        first_text = inputs(request)[0]
        with lock:
            first_request = first_text not in timed_out
            timed_out.add(first_text)
        if first_request and first_text.startswith("call 0 "):
            raise httpx2.ReadTimeout("timed out", request=request)
        return gateway_reply(request)

    sent = serve(web, reply)
    engine = gateway_engine(batch_size=4)

    with clock.concurrent_sleeps(2):
        first_call = _batch_sizes(engine, sent, 0, 8)
    second_call = _batch_sizes(engine, sent, 1, 8)

    assert [first_call, second_call] == [[4, 4, 4, 4], [2, 2, 2, 2]]


def test_fast_batches_grow_the_batch_size_once_per_cooldown_up_to_the_configured_size(
    clock: ClockFake, web: WebFake
) -> None:
    """After a change of the batch size, fast batches grow it only when the cooldown has passed.

    A slow batch halves the size from six texts to three. Fast batches in the cooldown do not
    grow it. After the cooldown, two fast batches grow it by two texts, and the cooldown starts
    again. The size grows to the configured six texts, and not more.
    """
    node = _TimedNode(clock, _SLOW_BATCH_SECONDS)
    sent = serve(web, node.reply)
    engine = EmbeddingsEngine(ollama_config(), valkey_client=None, batch_size=6)
    cooldown = defaults.DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS

    sizes = [_batch_sizes(engine, sent, 0, 6)]
    node.seconds = [0.0]
    sizes.append(_batch_sizes(engine, sent, 1, 6))
    clock.shift(cooldown)
    sizes.append(_batch_sizes(engine, sent, 2, 6))
    sizes.append(_batch_sizes(engine, sent, 3, 6))
    clock.shift(cooldown)
    sizes.append(_batch_sizes(engine, sent, 4, 6))
    clock.shift(cooldown)
    sizes.append(_batch_sizes(engine, sent, 5, 12))

    assert sizes == [[6], [3, 3], [3, 3], [5, 1], [5, 1], [6, 6]]


def test_only_a_batch_within_the_margin_below_the_latency_threshold_counts_as_fast(
    clock: ClockFake, web: WebFake
) -> None:
    """A batch counts toward growth only when it takes at most the margin share of the threshold.

    One worker sends the batches, so each latency is the latency of one batch. After a decrease
    and the cooldown, a batch at the margin counts as fast. A batch slower than the margin but not
    slower than the threshold stops the run of fast batches. The size grows only after two fast
    batches in a row.
    """
    ai_cfg = ollama_config()
    ai_cfg.ollama_max_parallel = 1
    node = _TimedNode(clock, _SLOW_BATCH_SECONDS)
    sent = serve(web, node.reply)
    engine = EmbeddingsEngine(ai_cfg, valkey_client=None, batch_size=4)
    threshold = defaults.DEFAULT_RAG_EMBEDDING_LATENCY_THRESHOLD_SECONDS
    margin = threshold * defaults.DEFAULT_RAG_EMBEDDING_INCREASE_LATENCY_RATIO

    sizes = [_batch_sizes(engine, sent, 0, 4)]
    clock.shift(defaults.DEFAULT_RAG_EMBEDDING_INCREASE_COOLDOWN_SECONDS)
    node.seconds = [margin, (margin + threshold) / 2, margin]
    sizes.append(_batch_sizes(engine, sent, 1, 6))
    node.seconds = [margin]
    sizes.append(_batch_sizes(engine, sent, 2, 6))
    sizes.append(_batch_sizes(engine, sent, 3, 6))

    assert sizes == [[4], [2, 2, 2], [2, 2, 2], [4, 2]]
