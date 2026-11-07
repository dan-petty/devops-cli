"""Embedding through Ollama, OpenAI-compatible and gateway endpoints: URLs, keys, options, retries."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.constants import (
    CONST_RAG_MAX_CHUNK_TOKENS,
)
from devops_cli.config.settings import AIConfig
from tests.support.embedding_replies import (
    answer_posts,
    capture_embedding_posts,
    ollama_config,
    ollama_reply,
    serve,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_ollama_embeddings_success(web: WebFake) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(200, json={"embedding": [0.1] * 384})

    answer_posts(web, fake_post)
    ai_cfg = AIConfig(
        provider="ollama", ollama_urls=["http://localhost:11434"], allow_private_network=True
    )
    engine = EmbeddingsEngine(ai_cfg)
    embs = engine.embed_texts(["sample text"])
    assert len(embs) == 1
    assert len(embs[0]) == 384


def test_openai_embeddings_success(web: WebFake) -> None:
    def fake_post(url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.2] * 1536}]},
        )

    answer_posts(web, fake_post)
    ai_cfg = AIConfig(provider="openai", allow_private_network=True)
    engine = EmbeddingsEngine(ai_cfg, api_key="mock-test-key")
    embs = engine.embed_texts(["sample text"])
    assert len(embs) == 1
    assert len(embs[0]) == 1536


def test_gateway_embeddings_use_gateway_url_not_global_api_base(
    web: WebFake,
) -> None:
    """Verify provider gateway embeds via gateway_url with the model unchanged."""
    calls = capture_embedding_posts(web)
    ai_cfg = AIConfig(
        provider="gateway",
        gateway_url="http://example.com:4000/v1",
        api_base_url="http://example.com:1234/v1",
        allow_private_network=True,
    )
    ai_cfg.tasks.embedding.model = "devops-embedding"

    embs = EmbeddingsEngine(ai_cfg, api_key="sk-gateway").embed_texts(["hello"])

    assert (calls[-1], len(embs[0])) == (
        ("http://example.com:4000/v1/embeddings", "Bearer sk-gateway", "devops-embedding"),
        8,
    )


def test_gateway_embeddings_prefer_task_api_base_url(web: WebFake) -> None:
    """Verify an embedding task's own api_base_url overrides the gateway URL."""
    calls = capture_embedding_posts(web)
    ai_cfg = AIConfig(
        provider="gateway", gateway_url="http://example.com:4000/v1", allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "devops-embedding"
    ai_cfg.tasks.embedding.api_base_url = "http://example.com:9000/v1"

    EmbeddingsEngine(ai_cfg, api_key="sk-gateway").embed_texts(["hello"])

    assert calls[-1][0] == "http://example.com:9000/v1/embeddings"


def test_gateway_embedding_task_ignores_global_openai_base_url(
    web: WebFake,
) -> None:
    """Verify an embedding task on the gateway never embeds via another provider's base URL."""
    calls = capture_embedding_posts(web)
    ai_cfg = AIConfig(
        provider="openai",
        api_base_url="https://api.example.com/v1",
        gateway_url="http://example.com:4000/v1",
        allow_private_network=True,
    )
    ai_cfg.tasks.embedding.provider = "gateway"
    ai_cfg.tasks.embedding.model = "devops-embedding"

    EmbeddingsEngine(ai_cfg, api_key="sk-gateway").embed_texts(["hello"])

    assert calls[-1][0] == "http://example.com:4000/v1/embeddings"


def test_openai_embeddings_retries_transient_connection_reset(
    clock: ClockFake,
    web: WebFake,
) -> None:
    """A transient ReadError, such as a connection reset, gets one more attempt after a backoff."""
    attempts = 0

    def mock_post(url: str, **kwargs: Any) -> httpx2.Response:
        nonlocal attempts
        if "/embeddings" not in url:
            return httpx2.Response(200, json={}, request=httpx2.Request("POST", url))
        attempts += 1
        if attempts == 1:
            raise httpx2.ReadError("[Errno 104] Connection reset by peer")
        return httpx2.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.25] * 8}]},
            request=httpx2.Request("POST", url),
        )

    answer_posts(web, mock_post)
    ai_cfg = AIConfig(
        provider="gateway", gateway_url="http://example.com:4000/v1", allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    engine = EmbeddingsEngine(ai_cfg, api_key="sk-test", valkey_client=None)

    vecs = engine.embed_texts(["retry me"])

    assert (attempts, len(vecs[0]), len(clock.waits)) == (2, 8, 1)


def test_openai_embeddings_retries_http_429(web: WebFake) -> None:
    """HTTP 429 rate limit responses are retried with Retry-After backoff."""
    attempts = 0

    def mock_post(url: str, **kwargs: Any) -> httpx2.Response:
        nonlocal attempts
        if "/embeddings" not in url:
            return httpx2.Response(200, json={}, request=httpx2.Request("POST", url))
        attempts += 1
        if attempts == 1:
            return httpx2.Response(429, headers={"retry-after": "0"}, text="rate limited")
        return httpx2.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.75] * 8}]},
            request=httpx2.Request("POST", url),
        )

    answer_posts(web, mock_post)
    ai_cfg = AIConfig(
        provider="gateway", gateway_url="http://example.com:4000/v1", allow_private_network=True
    )
    ai_cfg.tasks.embedding.model = "bge-m3:latest"
    engine = EmbeddingsEngine(ai_cfg, api_key="sk-test", valkey_client=None)

    vecs = engine.embed_texts(["rate limit me"])

    assert (attempts, len(vecs[0])) == (2, 8)


def test_ollama_embed_batch_sends_num_ctx_option(web: WebFake) -> None:
    """A direct Ollama embedding batch request passes options.num_ctx defaulting to 8192."""
    sent = serve(web, ollama_reply)
    engine = EmbeddingsEngine(ollama_config(), valkey_client=None)

    engine.embed_texts(["hello world"])

    assert len(sent) == 1
    body = json.loads(sent[0].content)
    assert body.get("options") == {"num_ctx": CONST_RAG_MAX_CHUNK_TOKENS}


def test_ollama_embed_batch_sends_configured_num_ctx(web: WebFake) -> None:
    """A direct Ollama embedding batch request passes configured num_ctx."""
    sent = serve(web, ollama_reply)
    ai_cfg = ollama_config()
    ai_cfg.tasks.embedding.num_ctx = 4096
    engine = EmbeddingsEngine(ai_cfg, valkey_client=None)

    engine.embed_texts(["hello world"])

    assert len(sent) == 1
    body = json.loads(sent[0].content)
    assert body.get("options") == {"num_ctx": 4096}


def test_an_openai_engine_without_a_key_reads_it_from_the_keyring(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    keyring_store.values["ai_api_key"] = "sk-from-keyring"

    engine = EmbeddingsEngine(
        AIConfig(provider="openai", allow_private_network=True), valkey_client=None
    )

    assert engine.api_key == "sk-from-keyring"
