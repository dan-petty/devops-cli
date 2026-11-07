"""What an embedding call raises when a provider cannot answer, and what it leaves behind."""

from __future__ import annotations

import re
from typing import Any

import httpx2
import pytest
from fakeredis import FakeServer, FakeValkey

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.config.settings import AIConfig
from devops_cli.valkey.client import ValkeyClient
from tests.support.embedding_replies import (
    SERVING_BACKEND,
    answer_posts,
    gateway_engine,
    inputs,
    ollama_engine,
    serve,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_no_provider_configured_raises_and_caches_nothing(
    valkey_server: FakeServer, valkey_client: ValkeyClient
) -> None:
    """With no provider and no Ollama URLs, embedding raises rather than inventing a vector."""
    engine = EmbeddingsEngine(
        AIConfig(provider="custom", ollama_urls=[]), valkey_client=valkey_client
    )

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["hello world", "test query"])

    assert (
        raised.value.message,
        raised.value.details,
        FakeValkey(server=valkey_server).dbsize(),
    ) == (
        f"Embedding model {engine.model} has no provider: the embedding task's provider 'custom' "
        "is not ollama, openai, copilot or gateway, and no Ollama URLs are set. "
        "Set ai.tasks.embedding.provider",
        {"model": engine.model, "provider": "custom"},
        0,
    )


def test_ollama_provider_with_no_url_raises_embeddings_error_naming_the_setting(
    valkey_server: FakeServer, valkey_client: ValkeyClient
) -> None:
    """With the Ollama provider and no Ollama URL, embedding raises an error that names the setting."""
    engine = EmbeddingsEngine(
        AIConfig(provider="ollama", ollama_urls=[]), valkey_client=valkey_client
    )

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["hello world"])

    assert (
        raised.value.message,
        raised.value.details,
        FakeValkey(server=valkey_server).dbsize(),
    ) == (
        f"Embedding model {engine.model} has no Ollama URL: ai.provider is 'ollama' and "
        "ai.ollama_urls is empty. Set ai.ollama_urls",
        {"model": engine.model, "provider": "ollama"},
        0,
    )


def test_ollama_raises_after_every_node_fails(web: WebFake) -> None:
    """When every node fails a single text, the error names the model and each node's failure.

    The batch of two is halved once, and the first text failing everywhere ends the call: no
    further request is sent for the second text.
    """
    posts: list[str] = []

    def fake_post(url: str, **kwargs: Any) -> httpx2.Response:
        if url.endswith("/api/embed"):
            posts.append(url)
        if url.startswith("http://example.com:11434/"):
            return httpx2.Response(404, json={"error": 'model "bge-m3" not found'})
        raise httpx2.ConnectError("connection refused")

    answer_posts(web, fake_post)
    engine = ollama_engine(["http://example.com:11434", "http://example.com:11435"])

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["first chunk", "second chunk"])

    assert (raised.value.message, raised.value.details["model"], len(posts)) == (
        "Embedding model bge-m3 produced no embeddings: "
        "http://example.com:11434/api/embed answered HTTP 404: "
        '{"error":"model \\"bge-m3\\" not found"}; '
        "http://example.com:11435/api/embed failed: ConnectError: connection refused",
        "bge-m3",
        4,
    )


@pytest.mark.parametrize("userinfo", ["bench-user:FAKE-2481-value", "FAKE-2481-value"])
def test_an_embedding_error_names_its_endpoint_without_the_userinfo_of_the_url(
    userinfo: str, web: WebFake
) -> None:
    """The endpoint that an error names is the URL without its userinfo, which the client sends
    as Basic authentication: a password and a user name alone, such as a token, stay out (#2481)."""

    def fake_post(url: str, **kwargs: Any) -> httpx2.Response:
        if httpx2.URL(url).port == 11434:
            return httpx2.Response(500, json={"error": "model failed"})
        raise httpx2.ConnectError("connection refused")

    answer_posts(web, fake_post)
    engine = ollama_engine([f"http://{userinfo}@example.com:11434", "http://example.com:11435"])

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["first chunk"])

    assert (raised.value.message, "FAKE-2481-value" in repr(raised.value.details)) == (
        "Embedding model bge-m3 produced no embeddings: "
        'http://example.com:11434/api/embed answered HTTP 500: {"error":"model failed"}; '
        "http://example.com:11435/api/embed failed: ConnectError: connection refused",
        False,
    )


def test_ollama_parallel_batches_raise_when_one_fails_everywhere(
    web: WebFake,
) -> None:
    """Batches embedded in parallel fail the call with the failing batch's EmbeddingsError."""

    def fake_post(url: str, **kwargs: Any) -> httpx2.Response:
        if "unservable" in kwargs["json"]["input"][0]:
            return httpx2.Response(404, json={"error": "model not found"})
        return httpx2.Response(
            200, json={"embeddings": [[0.5] * 4 for _ in kwargs["json"]["input"]]}
        )

    answer_posts(web, fake_post)
    engine = ollama_engine(["http://example.com:11434"], batch_size=1)

    with pytest.raises(EmbeddingsError, match=re.escape("answered HTTP 404")):
        engine.embed_texts(["chunk one", "unservable chunk", "chunk three"])


@pytest.mark.parametrize(
    ("reply", "failure", "waits"),
    [
        (
            httpx2.Response(
                400, json={"error": {"message": "model 'bge-m3:latest' is not loaded"}}
            ),
            'answered HTTP 400: {"error":{"message":"model \'bge-m3:latest\' is not loaded"}}',
            0,
        ),
        (httpx2.Response(200, json={"data": []}), "returned 0 embeddings for 1 texts", 0),
        (
            httpx2.Response(200, text="<html>bad gateway</html>"),
            "returned 0 embeddings for 1 texts",
            0,
        ),
        (
            httpx2.ConnectError("connection refused"),
            "failed: ConnectError: connection refused",
            3,
        ),
    ],
    ids=["http-400", "no-data", "not-json", "unreachable"],
)
def test_gateway_failures_raise_naming_model_endpoint_and_error(
    clock: ClockFake,
    reply: httpx2.Response | Exception,
    failure: str,
    waits: int,
    web: WebFake,
) -> None:
    """A gateway that answers with an error, a malformed reply or not at all raises.

    An unreachable gateway is retried: each backoff returns at once and is recorded.
    """

    def fake_post(url: str, **kwargs: Any) -> httpx2.Response:
        if isinstance(reply, Exception):
            raise reply
        return reply

    answer_posts(web, fake_post)
    ai_cfg = AIConfig(provider="gateway", gateway_url="https://example.com/v1")
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    engine = EmbeddingsEngine(ai_cfg, api_key="sk-gateway", valkey_client=None)

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_query("where is the retry policy")

    assert (raised.value.message, raised.value.details["model"], len(clock.waits)) == (
        "Embedding model bge-m3:latest produced no embeddings: "
        f"https://example.com/v1/embeddings {failure}",
        "bge-m3:latest",
        waits,
    )


def test_openai_embeddings_does_not_retry_http_400(web: WebFake) -> None:
    """Non-transient HTTP 400 client errors fail immediately without retry loops."""
    attempts = 0

    def mock_post(url: str, **kwargs: Any) -> httpx2.Response:
        nonlocal attempts
        if "/embeddings" not in url:
            return httpx2.Response(200, json={}, request=httpx2.Request("POST", url))
        attempts += 1
        return httpx2.Response(400, text="Bad Request", request=httpx2.Request("POST", url))

    answer_posts(web, mock_post)
    ai_cfg = AIConfig(
        provider="gateway", gateway_url="http://example.com:4000/v1", allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    engine = EmbeddingsEngine(ai_cfg, api_key="sk-test", valkey_client=None)

    with pytest.raises(EmbeddingsError) as raised:
        engine.embed_texts(["bad request"])
    assert raised.value.error_code == "EMBEDDINGS_ERROR"

    assert attempts == 1


def test_a_gateway_with_no_deployment_left_gives_a_transient_error(
    web: WebFake, clock: ClockFake
) -> None:
    """A 429 'No deployments available' counts as transient, so a caller skips and goes on."""
    serve(web, lambda request: httpx2.Response(429, text="No deployments available"))

    with pytest.raises(EmbeddingsError, match="No deployments available") as raised:
        gateway_engine().embed_texts(["one"])

    assert raised.value.is_transient is True


def test_a_gateway_that_gives_fewer_vectors_than_texts_raises_naming_both_counts(
    web: WebFake,
) -> None:
    """Two texts and one vector in the reply raise, so no text gets the vector of another."""
    serve(
        web,
        lambda request: httpx2.Response(200, json={"data": [{"index": 0, "embedding": [0.5] * 4}]}),
    )

    with pytest.raises(EmbeddingsError, match="returned 1 embeddings for 2 texts"):
        gateway_engine().embed_texts(["first text", "second text"])


def test_an_ollama_node_that_gives_fewer_vectors_than_texts_gets_the_batch_cut(
    web: WebFake,
) -> None:
    """The node gives one vector for two texts, so the batch is cut and each text gets its own."""
    sent = serve(web, lambda request: httpx2.Response(200, json={"embeddings": [[0.5] * 4]}))

    vectors = ollama_engine([SERVING_BACKEND]).embed_texts(["first text", "second text"])

    assert (vectors, [len(inputs(request)) for request in sent]) == ([[0.5] * 4] * 2, [2, 1, 1])
