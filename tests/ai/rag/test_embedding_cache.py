"""The memory cache and the Valkey tier of an embeddings engine."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fakeredis import FakeServer, FakeValkey

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.telemetry.instruments import EMBEDDING_CACHE_LOOKUPS_TOTAL
from devops_cli.valkey.client import ValkeyClient
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
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_a_text_the_memory_cache_holds_is_not_sent_again(web: WebFake) -> None:
    sent = serve(web, ollama_reply)
    engine = ollama_engine([SERVING_BACKEND])

    first = engine.embed_texts(["hello", "world"])
    second = engine.embed_texts(["hello", "world"])

    assert (len(sent), first == second) == (1, True)


def test_a_query_is_served_from_the_memory_cache_on_the_second_call(web: WebFake) -> None:
    sent = serve(web, ollama_reply)
    engine = ollama_engine([SERVING_BACKEND])

    first = engine.embed_query("test query")
    second = engine.embed_query("test query")

    assert (len(sent), first == second) == (1, True)


def test_the_memory_cache_drops_the_text_used_least_recently(web: WebFake) -> None:
    """With room for two vectors, a third text pushes out the one that no call asked for lately."""
    sent = serve(web, ollama_reply)
    engine = ollama_engine([SERVING_BACKEND], cache_size=2)

    for text in ("a", "b", "a", "c", "a", "b"):
        engine.embed_texts([text])

    assert [inputs(request) for request in sent] == [["a"], ["b"], ["c"], ["b"]]


def test_the_memory_cache_holds_one_intake_comparison_set(web: WebFake) -> None:
    """An intake run embeds about 1,800 texts; a second call in the same process sends none."""
    sent = serve(web, gateway_reply)
    engine = gateway_engine()
    texts = [f"item {number}" for number in range(1800)]
    engine.embed_texts(texts)
    first_run = len(sent)

    engine.embed_texts(texts)

    assert len(sent) == first_run


def test_a_second_engine_reads_vectors_from_valkey_and_sends_nothing(
    valkey_client: ValkeyClient, web: WebFake
) -> None:
    """The memory cache of the second engine is empty, and Valkey holds the vector."""
    sent = serve(web, ollama_reply)
    config = ollama_config()
    first = EmbeddingsEngine(config, valkey_client=valkey_client).embed_texts(["pre-cached chunk"])

    second = EmbeddingsEngine(config, valkey_client=valkey_client).embed_texts(["pre-cached chunk"])

    assert (len(sent), second == first) == (1, True)


def test_a_fresh_vector_is_stored_in_valkey_for_a_week(
    valkey_server: FakeServer, valkey_client: ValkeyClient, web: WebFake
) -> None:
    serve(web, ollama_reply)
    engine = EmbeddingsEngine(ollama_config(), valkey_client=valkey_client)

    vectors = engine.embed_texts(["newly generated chunk"])

    valkey = FakeValkey(server=valkey_server, decode_responses=True)
    (key,) = valkey.keys("*")
    assert (json.loads(valkey.get(key)), valkey.ttl(key)) == (vectors[0], 604800)


def test_a_document_and_a_query_of_one_text_have_two_valkey_keys(
    valkey_server: FakeServer, valkey_client: ValkeyClient, web: WebFake
) -> None:
    """The same text under a query prompt and under a document prompt is two vectors."""
    sent = serve(web, ollama_reply)
    config = ollama_config()
    config.tasks.embedding.model = "nomic-embed-text"
    engine = EmbeddingsEngine(config, valkey_client=valkey_client)

    engine.embed_texts(["sample text"], is_query=False)
    engine.embed_texts(["sample text"], is_query=True)

    assert (
        FakeValkey(server=valkey_server).dbsize(),
        [inputs(request) for request in sent],
    ) == (2, [["search_document: sample text"], ["search_query: sample text"]])


def test_a_second_engine_reads_a_vector_of_a_prompted_model_from_valkey(
    valkey_client: ValkeyClient, web: WebFake
) -> None:
    """The Valkey key follows the text with its prompt, so a model with a prompt gets its hit."""
    sent = serve(web, ollama_reply)
    config = ollama_config()
    config.tasks.embedding.model = "nomic-embed-text"
    first = EmbeddingsEngine(config, valkey_client=valkey_client).embed_texts(["shared chunk"])

    second = EmbeddingsEngine(config, valkey_client=valkey_client).embed_texts(["shared chunk"])

    assert (len(sent), second == first) == (1, True)


def test_the_same_text_under_two_prompts_is_two_cache_misses(web: WebFake) -> None:
    """The cache keys hash the text after its prompt is applied."""
    sent = serve(web, ollama_reply)
    config = ollama_config()
    config.tasks.embedding.model = "qwen3-embedding"
    engine = EmbeddingsEngine(config, valkey_client=None)

    engine.embed_texts(["common content"])
    engine.embed_query("common content")

    assert [inputs(request) for request in sent] == [
        ["common content"],
        [
            "Instruct: Given a code search query, retrieve relevant code or documentation\n"
            "Query: common content"
        ],
    ]


def _valkey_cache_cooldown() -> float:
    """The cooldown of the breaker of the Valkey cache tier, in seconds.

    The import is local, so the module loads on a base without the default.
    """
    from devops_cli.config.defaults import DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS

    return DEFAULT_VALKEY_CACHE_BREAKER_COOLDOWN_SECONDS


def test_a_valkey_outage_turns_the_embedding_l2_cache_off_for_a_cooldown(
    valkey_server: FakeServer,
    valkey_client: ValkeyClient,
    clock: ClockFake,
    web: WebFake,
) -> None:
    """A failed read sends texts to the provider for the cooldown; a read after it serves from Valkey.

    A first engine embeds three texts, which puts their vectors in Valkey. A second engine, with an
    empty memory cache, then embeds one of them in each phase, so each request that the provider
    receives is a text that Valkey did not answer.
    """
    sent = serve(web, gateway_reply)
    EmbeddingsEngine(
        gateway_config(), api_key="sk-gateway", valkey_client=valkey_client
    ).embed_texts(["in the outage", "in the cooldown", "after the cooldown"])
    engine = EmbeddingsEngine(gateway_config(), api_key="sk-gateway", valkey_client=valkey_client)

    valkey_server.connected = False
    engine.embed_texts(["in the outage"])
    valkey_server.connected = True
    engine.embed_texts(["in the cooldown"])
    clock.shift(_valkey_cache_cooldown())
    engine.embed_texts(["after the cooldown"])

    assert [inputs(request) for request in sent] == [
        ["in the outage", "in the cooldown", "after the cooldown"],
        ["in the outage"],
        ["in the cooldown"],
    ]


def test_an_engine_whose_valkey_refuses_embeds_and_dials_it_once_in_each_cooldown(
    monkeypatch: pytest.MonkeyPatch,
    unexpected_loopback_connects: list[str],
    clock: ClockFake,
    web: WebFake,
) -> None:
    """The configured Valkey refuses each connection, and the engine embeds with no Valkey tier.

    A service binds and listens on the configured port through the C socket type, as a
    port-forward to a live Valkey does, so the kernel would accept a connection. The guard refuses
    each dial and reports it, and the service sees no connection. The first refused read opens the
    breaker, so the second call dials nothing, and the call after the cooldown dials once more.
    """
    import _socket
    import socket

    from devops_cli.config.settings import reset_settings_cache

    sent = serve(web, gateway_reply)
    with socket.socket() as service:
        _socket.socket.bind(service, ("127.0.0.1", 0))
        _socket.socket.listen(service)
        service.setblocking(False)
        port = service.getsockname()[1]
        monkeypatch.setenv("DEVOPS_CLI_VALKEY_URL", f"valkey://127.0.0.1:{port}")
        reset_settings_cache()
        engine = EmbeddingsEngine(gateway_config(), api_key="sk-gateway")
        try:
            engine.embed_texts(["first"])
            engine.embed_texts(["second"])
            dials_in_the_cooldown = list(unexpected_loopback_connects)
            clock.shift(_valkey_cache_cooldown())
            engine.embed_texts(["third"])
            dials = list(unexpected_loopback_connects)
            with pytest.raises(BlockingIOError) as raised:
                service.accept()
            assert raised.value is not None
        finally:
            unexpected_loopback_connects.clear()
    dial = f"127.0.0.1:{port} (MainThread)"
    assert (len(sent), dials_in_the_cooldown, dials) == (3, [dial], [dial, dial])


def _lookups(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    """The points of the embedding cache lookup counter, hits before misses."""
    return sorted(
        otlp.points(EMBEDDING_CACHE_LOOKUPS_TOTAL.name), key=lambda point: point[0]["result"]
    )


def test_an_embedding_request_counts_each_text_once_by_its_cache_result(
    otlp: FakeCollector, web: WebFake
) -> None:
    """Three texts that the memory cache holds and two that it does not are three hits and two
    misses, each sent one time."""
    serve(web, gateway_reply)
    engine = gateway_engine()
    engine.embed_texts(["first", "second", "third"])
    otlp.clear()

    engine.embed_texts(["first", "second", "third", "fourth", "fifth"])

    assert _lookups(otlp) == [
        ({"result": "hit", "tier": "memory"}, 3.0),
        ({"result": "miss"}, 2.0),
    ]


def test_a_text_that_only_valkey_holds_counts_as_a_valkey_hit(
    otlp: FakeCollector, valkey_client: ValkeyClient, web: WebFake
) -> None:
    """A second process finds the text in Valkey and not in its own memory cache."""
    serve(web, gateway_reply)
    config = gateway_config()
    EmbeddingsEngine(config, api_key="sk-gateway", valkey_client=valkey_client).embed_texts(
        ["shared chunk"]
    )
    otlp.clear()

    EmbeddingsEngine(config, api_key="sk-gateway", valkey_client=valkey_client).embed_texts(
        ["shared chunk"]
    )

    assert _lookups(otlp) == [({"result": "hit", "tier": "valkey"}, 1.0)]


def test_a_direct_openai_key_is_no_hit_for_the_gateway(
    valkey_client: ValkeyClient, web: WebFake
) -> None:
    """A direct OpenAI request sends `text-embedding-3-small`, and the gateway sends the
    configured name, so the direct vector is no hit for the gateway (#4569)."""
    from devops_cli.config.settings import AIConfig

    sent = serve(web, gateway_reply)
    direct = AIConfig(
        provider="openai", api_base_url="http://example.com:1234/v1", allow_private_network=True
    )
    direct.tasks.embedding.model = "qwen3-embedding:0.6b"
    gateway = gateway_config()
    gateway.tasks.embedding.model = "qwen3-embedding:0.6b"

    EmbeddingsEngine(direct, valkey_client=valkey_client).embed_texts(["same text"])
    EmbeddingsEngine(gateway, api_key="sk-gateway", valkey_client=valkey_client).embed_texts(
        ["same text"]
    )

    assert [json.loads(request.content)["model"] for request in sent] == [
        "text-embedding-3-small",
        "qwen3-embedding:0.6b",
    ]
