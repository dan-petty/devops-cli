"""The AI client reads a reply's body only up to its size limit, through every provider, and
sends a gateway chat call only once it holds one of the gateway's backend slots.

Replies are answered by httpx2's own `MockTransport` with bodies that record how many of their
chunks were read, so no socket is opened. Hosts are `example.com`, as docs/TESTING.md requires.
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import AIClientError, LLMClient, network
from devops_cli.ai.client.network import request_limited_json, size_limit_text
from devops_cli.ai.client.streaming import StreamingTokenProcessor
from devops_cli.config.defaults import DEFAULT_GATEWAY_REVIEW_CONCURRENCY
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import OPENAI_DONE, RecordedBody, openai_chunk, route_client
from tests.llm_stream_fakes import reply as stream_reply
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

_LIMIT = 4096
_KIB = b"x" * 1024
_MESSAGES = [ChatMessage(role="user", content="hi")]
_OLLAMA = AIConfig(provider="ollama", ollama_urls=["http://example.com:11434"])
_OPENAI = AIConfig(provider="openai", api_base_url="https://example.com/v1")

# Each provider call that reads its reply under the size limit: (its client's config, the call).
_PROVIDER_CALLS: dict[str, tuple[AIConfig, Callable[[LLMClient], Any]]] = {
    "ollama-chat": (_OLLAMA, lambda client: client._ollama_messages("sys", _MESSAGES)),
    "ollama-tags": (_OLLAMA, lambda client: client._ollama_models()),
    "openai-chat": (_OPENAI, lambda client: client._openai_compat_messages("sys", _MESSAGES)),
    "openai-models": (_OPENAI, lambda client: client._openai_models()),
}


# A chat call reads its reply as SSE frames (#2365), so its 2 MB reply is 2,000 chunks of 1 KiB.
_REPLY_FRAMES: dict[str, list[bytes]] = {"openai-chat": [openai_chunk("x" * 1024)] * 2000}


@pytest.fixture
def small_limit(monkeypatch: pytest.MonkeyPatch) -> int:
    """Lower the reply size limit every provider call reads under to 4 KiB."""
    monkeypatch.setattr(network, "DEFAULT_AI_MAX_RESPONSE_BYTES", _LIMIT)
    return _LIMIT


def _answer(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


@pytest.mark.parametrize("call", list(_PROVIDER_CALLS))
@pytest.mark.usefixtures("public_dns")
def test_post_limited_json_stops_reading_past_limit(
    call: str, small_limit: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a provider stops reading a 2 MB reply once it passes the 4 KiB limit."""
    config, invoke = _PROVIDER_CALLS[call]
    client = LLMClient(config, api_key="sk-test", cache_enabled=False)
    body = RecordedBody(_REPLY_FRAMES.get(call, [_KIB] * 2000))
    route_client(client, monkeypatch, lambda request: httpx2.Response(200, content=iter(body)))

    with pytest.raises(AIClientError) as caught:
        invoke(client)

    assert (str(caught.value), body.read <= 5) == (
        "Response body exceeded maximum size (4KB).",
        True,
    )


def test_a_declared_length_past_the_limit_is_refused_unread() -> None:
    """Verify a Content-Length over the limit is refused before any of the body is read."""
    body = RecordedBody([_KIB] * 8)
    declared = {"content-length": str(8 * len(_KIB))}

    with (
        _answer(
            lambda request: httpx2.Response(200, headers=declared, content=iter(body))
        ) as client,
        pytest.raises(AIClientError, match=r"exceeded maximum size \(4KB\)"),
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat", limit_bytes=_LIMIT)

    assert body.read == 0


def test_a_compressed_reply_counts_its_decoded_bytes() -> None:
    """Verify the limit bounds the decoded body, so a small gzip reply cannot inflate past it."""
    packed = gzip.compress(json.dumps({"content": "x" * 100_000}).encode())
    headers = {"content-encoding": "gzip"}

    with (
        _answer(lambda request: httpx2.Response(200, headers=headers, content=packed)) as client,
        pytest.raises(AIClientError, match=r"exceeded maximum size \(4KB\)"),
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat", limit_bytes=_LIMIT)

    assert len(packed) < _LIMIT


def test_a_reply_within_the_limit_is_parsed_with_its_headers() -> None:
    """Verify a JSON object reply comes back parsed, with the headers it was sent with."""
    reply = httpx2.Response(200, headers={"x-served-by": "node-a"}, json={"model": "m"})

    with _answer(lambda request: reply) as client:
        payload, headers = request_limited_json(client, "GET", "http://example.com/v1/models")

    assert (payload, headers.get("x-served-by")) == ({"model": "m"}, "node-a")


def test_an_error_reply_raises_with_its_body_readable() -> None:
    """Verify a 4xx reply is never parsed and its body reaches the HTTPStatusError's response."""
    error = {"error": "model 'm' does not support thinking"}

    with (
        _answer(lambda request: httpx2.Response(400, json=error)) as client,
        pytest.raises(httpx2.HTTPStatusError) as caught,
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat")

    assert (caught.value.response.status_code, caught.value.response.json()) == (400, error)


def test_an_error_reply_past_the_limit_is_not_read_whole() -> None:
    """Verify a 5xx reply's body is bounded by the same limit as a success."""
    body = RecordedBody([_KIB] * 2000)

    with (
        _answer(lambda request: httpx2.Response(500, content=iter(body))) as client,
        pytest.raises(AIClientError, match=r"exceeded maximum size \(4KB\)"),
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat", limit_bytes=_LIMIT)

    assert body.read <= 5


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not json", "Invalid JSON response payload from AI provider"),
        (b'["a", "b"]', "AI provider replied with a JSON list, not an object"),
    ],
)
def test_a_reply_that_is_not_a_json_object_is_refused(content: bytes, message: str) -> None:
    """Verify a body that is not JSON, or JSON that is not an object, raises AIClientError."""
    with (
        _answer(lambda request: httpx2.Response(200, content=content)) as client,
        pytest.raises(AIClientError, match=message),
    ):
        request_limited_json(client, "POST", "http://example.com/api/chat")


@pytest.mark.parametrize(
    ("limit_bytes", "text"),
    [
        (50 * 1024 * 1024, "50MB"),
        (1536 * 1024, "1.5MB"),
        (4096, "4KB"),
        (1536, "1.5KB"),
        (200, "200 bytes"),
    ],
)
def test_size_limit_text_names_the_largest_whole_unit(limit_bytes: int, text: str) -> None:
    """Verify a limit is named in MB, KB or bytes, never rounded down to 0MB."""
    assert size_limit_text(limit_bytes) == text


def test_the_stream_processor_names_its_limit_in_kb() -> None:
    """Verify the sanitizing stream processor's limit message names a sub-MB limit correctly."""
    processor = StreamingTokenProcessor(max_stream_bytes=_LIMIT)

    with pytest.raises(AIClientError) as caught:
        processor.feed("x" * (_LIMIT + 1))

    assert str(caught.value) == "Stream exceeded maximum size limit of 4KB."


def test_ollama_round_robin_index_lives_under_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify load_and_increment_rr_index writes under DEVOPS_CLI_DATA_DIR and nowhere in temp."""
    from devops_cli.ai.client.network import load_and_increment_rr_index

    data_dir = tmp_path / "custom_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))

    system_temp = Path(tempfile.gettempdir())
    uid = os.getuid() if hasattr(os, "getuid") else 0
    temp_target = system_temp / f"devops_cli_ollama_rr_{uid}"
    if temp_target.exists():
        temp_target.unlink()

    idx = load_and_increment_rr_index(3)
    expected_file = data_dir / f"devops_cli_ollama_rr_{uid}"

    assert (
        idx >= 0,
        expected_file.exists(),
        temp_target.exists(),
    ) == (True, True, False)


_GATEWAY = AIConfig(
    provider="gateway", gateway_url="http://example.com/v1", allow_private_network=True
)
_CHAT_REPLY = {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

# Each gateway chat call, plain and streamed.
_GATEWAY_CHAT_CALLS: dict[str, Callable[[LLMClient], Any]] = {
    "messages": lambda client: client._openai_compat_messages("sys", _MESSAGES),
    "stream": lambda client: list(client._openai_compat_stream("sys", _MESSAGES)),
}


@pytest.fixture
def short_slot_wait(monkeypatch: pytest.MonkeyPatch) -> float:
    """Lower the wait for a gateway slot to a few milliseconds."""
    monkeypatch.setattr(network, "DEFAULT_GATEWAY_SLOT_TIMEOUT_SECONDS", 0.01)
    return 0.01


@contextmanager
def _every_gateway_slot_held(but: int = 0) -> Iterator[None]:
    """Hold every gateway slot but `but` of them in this thread for the block."""
    with ExitStack() as slots:
        for _ in range(DEFAULT_GATEWAY_REVIEW_CONCURRENCY - but):
            slots.enter_context(network.acquire_gateway_slot())
        yield


def _a_further_request_is_refused() -> bool:
    """Whether a request for a gateway slot now waits past the timeout and is refused."""
    try:
        with network.acquire_gateway_slot():
            return False
    except AIClientError:
        return True


def test_gateway_slots_never_admit_more_than_the_slot_sum() -> None:
    """Verify eight threads through the gateway limiter never hold more than the slot sum."""
    in_flight = peak = entered = 0
    counter_lock = threading.Lock()
    limit = min(8, DEFAULT_GATEWAY_REVIEW_CONCURRENCY)
    barrier = threading.Barrier(limit)

    def hold_a_slot() -> None:
        nonlocal in_flight, peak, entered
        with network.acquire_gateway_slot():
            with counter_lock:
                in_flight += 1
                entered += 1
                peak = max(peak, in_flight)
                wait_at_barrier = entered <= limit
            if wait_at_barrier:
                barrier.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
            with counter_lock:
                in_flight -= 1

    threads = [threading.Thread(target=hold_a_slot) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert (peak, entered) == (min(peak, DEFAULT_GATEWAY_REVIEW_CONCURRENCY), 8)


@pytest.mark.usefixtures("short_slot_wait")
def test_a_wait_past_the_slot_timeout_names_the_slot_sum() -> None:
    """Verify a request that finds every gateway slot held past the timeout raises, naming the cap."""
    with _every_gateway_slot_held(), pytest.raises(AIClientError) as caught:
        with network.acquire_gateway_slot():
            pass

    assert f"{DEFAULT_GATEWAY_REVIEW_CONCURRENCY} backend slots" in str(caught.value)


@pytest.mark.parametrize("call", list(_GATEWAY_CHAT_CALLS))
@pytest.mark.usefixtures("public_dns", "short_slot_wait")
def test_a_gateway_chat_call_waits_for_a_gateway_slot(
    call: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a gateway chat call, streamed or not, sends nothing while every slot is held."""
    client = LLMClient(_GATEWAY, api_key="sk-test", cache_enabled=False)
    sent = route_client(client, monkeypatch, lambda request: httpx2.Response(200, json=_CHAT_REPLY))

    with _every_gateway_slot_held(), pytest.raises(AIClientError, match="backend slots"):
        _GATEWAY_CHAT_CALLS[call](client)

    assert sent == []


@pytest.mark.usefixtures("public_dns", "short_slot_wait")
def test_a_gateway_stream_holds_its_slot_until_the_generator_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an open gateway stream keeps its slot after its first chunk, so with every other
    slot held a further request is refused, and that closing the stream early gives it back."""
    client = LLMClient(_GATEWAY, api_key="sk-test", cache_enabled=False)
    route_client(
        client,
        monkeypatch,
        lambda request: stream_reply([openai_chunk("a"), openai_chunk("b"), OPENAI_DONE]),
    )

    with _every_gateway_slot_held(but=1):
        stream = client._openai_compat_stream("sys", _MESSAGES)
        first_chunk = next(stream)
        refused_while_open = _a_further_request_is_refused()
        stream.close()
        refused_once_closed = _a_further_request_is_refused()

    assert (first_chunk, refused_while_open, refused_once_closed) == ("a", True, False)


@pytest.mark.parametrize(
    "config",
    [_OPENAI, _OPENAI.model_copy(update={"gateway_enabled": True})],
    ids=["openai", "openai-with-gateway-enabled"],
)
@pytest.mark.usefixtures("public_dns", "short_slot_wait")
def test_another_provider_sends_while_every_gateway_slot_is_held(
    config: AIConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify an openai client's chat call takes no gateway slot, with `ai.gateway_enabled` set
    too: only the `gateway` provider sends chat calls to the gateway."""
    client = LLMClient(config, api_key="sk-test", cache_enabled=False)
    sent = route_client(client, monkeypatch, lambda request: httpx2.Response(200, json=_CHAT_REPLY))

    with _every_gateway_slot_held():
        reply = client._openai_compat_messages("sys", _MESSAGES)

    assert (reply.content, len(sent)) == ("ok", 1)


@pytest.mark.usefixtures("public_dns")
def test_dispatch_calls_hold_the_model_call_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify two dispatch calls, each slow on its send, keep only one model call in flight when
    the Service's limit is one, so a lane that waits holds the process, not the gateway (#2564)."""
    network.set_model_call_limit(1)
    client = LLMClient(_OPENAI, api_key="sk-test", cache_enabled=False)

    in_flight = peak = 0
    lock = threading.Lock()
    first_entered = threading.Event()
    release_first = threading.Event()

    def slow_send(request: httpx2.Request) -> httpx2.Response:
        nonlocal in_flight, peak
        with lock:
            in_flight += 1
            peak = max(peak, in_flight)
            is_first = peak == 1 and not first_entered.is_set()
        if is_first:
            first_entered.set()
            release_first.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
        with lock:
            in_flight -= 1
        return httpx2.Response(200, json=_CHAT_REPLY)

    sent = route_client(client, monkeypatch, slow_send)

    lanes = [
        threading.Thread(target=lambda: client._dispatch_messages("sys", _MESSAGES))
        for _ in range(2)
    ]
    for lane in lanes:
        lane.start()
    first_entered.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    release_first.set()
    for lane in lanes:
        lane.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert all(not lane.is_alive() for lane in lanes)
    assert (peak, len(sent)) == (1, 2)


def test_the_model_call_slot_admits_only_its_limit() -> None:
    """Verify four lanes, held in threads, keep at most the Service's limit in flight, and that
    every lane completes rather than failing when it waits for the slot (#2564)."""
    network.set_model_call_limit(2)
    in_flight = peak = 0
    lock = threading.Lock()
    two_in_flight = threading.Event()

    def hold_the_slot() -> None:
        nonlocal in_flight, peak
        with network.model_call_slot():
            with lock:
                in_flight += 1
                peak = max(peak, in_flight)
                if in_flight >= 2:
                    two_in_flight.set()
            if not two_in_flight.is_set():
                two_in_flight.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)
            with lock:
                in_flight -= 1

    threads = [threading.Thread(target=hold_the_slot) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    assert (peak, in_flight) == (2, 0)
