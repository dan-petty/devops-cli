"""The example config's own loopback RAG backends pass the SSRF guard; other private hosts do not.

`config.example.yaml` points Qdrant, Ollama and the gateway at localhost, enables RAG and leaves
`ai.allow_private_network` false. A loopback URL from the user's own config is the workstation
itself, so Qdrant, the embedding calls and the chat providers reach it; every other non-public
host still needs the setting. Replies come from a stubbed `httpx2.Client.post` (and
`httpx2.get`, `httpx2.post` for the Ollama provider), so no socket is opened.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx2
import pytest
import yaml

from devops_cli.ai.client import LLMClient
from devops_cli.ai.providers.ollama import OllamaProvider
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.config.constants import CONST_AI_ALLOW_PRIVATE_NETWORK_ENV
from devops_cli.config.settings import Settings
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.models.ai import ChatMessage

EXAMPLE_CONFIG = Path(__file__).resolve().parents[1] / "config.example.yaml"


@pytest.fixture
def example_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings loaded from `config.example.yaml`, with no private-network override set."""
    monkeypatch.delenv(CONST_AI_ALLOW_PRIVATE_NETWORK_ENV, raising=False)
    return Settings.model_validate(yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8")))


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Answer every `httpx2.Client.post` with one embedding in both reply shapes; record the
    embedding URLs, not the telemetry exporter's, which shares the client."""
    urls: list[str] = []

    def answer(_client: httpx2.Client, url: str, **_kwargs: Any) -> httpx2.Response:
        if url.endswith(("/api/embed", "/embeddings")):
            urls.append(url)
        body = {"embeddings": [[0.5, 0.25]], "data": [{"index": 0, "embedding": [0.5, 0.25]}]}
        return httpx2.Response(200, json=body, request=httpx2.Request("POST", url))

    monkeypatch.setattr(httpx2.Client, "post", answer)
    return urls


def test_the_example_config_reaches_its_loopback_rag_backends(
    example_settings: Settings, sent: list[str]
) -> None:
    """Verify Qdrant and the Ollama and gateway embedding calls accept the example's localhost."""
    ai = example_settings.ai
    gateway_ai = ai.model_copy(update={"provider": "gateway"})

    qdrant = QdrantClient(
        base_url=str(example_settings.qdrant.url),
        api_key="x",
        allow_private_network=ai.allow_private_network,
    )
    ollama_vectors = EmbeddingsEngine(ai_config=ai, valkey_client=None)._query_ollama_node_batch(
        ai.get_ollama_urls[0], ["x"]
    )
    gateway_vectors = EmbeddingsEngine(
        ai_config=gateway_ai, api_key="sk-test", valkey_client=None
    )._embed_openai(["x"])

    assert (
        ai.allow_private_network,
        ai.rag.enabled,
        qdrant.base_url,
        ollama_vectors,
        gateway_vectors,
        sent,
    ) == (
        False,
        True,
        "http://localhost:6333",
        [[0.5, 0.25]],
        [[0.5, 0.25]],
        ["http://localhost:11434/api/embed", "http://localhost:4000/v1/embeddings"],
    )


def test_the_example_config_probes_its_loopback_embedding_dimension(
    example_settings: Settings, sent: list[str]
) -> None:
    """Verify the Ollama and gateway dimension probes reach the example's localhost.

    Each probe swallows its errors at debug level, so a refused URL would only lose the
    model's dimension, silently.
    """
    ai = example_settings.ai
    gateway_ai = ai.model_copy(update={"provider": "gateway"})

    assert (
        EmbeddingsEngine(ai_config=ai, valkey_client=None)._probe_ollama_dimension(),
        EmbeddingsEngine(
            ai_config=gateway_ai, api_key="sk-test", valkey_client=None
        )._probe_openai_dimension(),
        sent,
    ) == (2, 2, ["http://localhost:11434/api/embed", "http://localhost:4000/v1/embeddings"])


def test_the_example_config_chat_providers_accept_its_loopback_endpoints(
    example_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the chat client and the Ollama provider take the same loopback endpoints."""
    ai = example_settings.ai
    gateway = LLMClient(ai.model_copy(update={"provider": "gateway"}), api_key="sk-test")
    reply = httpx2.Response(
        200, json={"message": {"content": "ok"}}, request=httpx2.Request("POST", "http://x")
    )
    tags = httpx2.Response(200, json={"models": []}, request=httpx2.Request("GET", "http://x"))
    monkeypatch.setattr(httpx2, "post", lambda url, **_kwargs: reply)
    monkeypatch.setattr(httpx2, "get", lambda url, **_kwargs: tags)

    assert (
        LLMClient(ai)._validate_base_url(ai.get_ollama_urls[0], purpose="Ollama"),
        gateway._api_base(),
        OllamaProvider(ai).generate([ChatMessage(role="user", content="hi")]),
        OllamaProvider(ai).is_available(),
    ) == (
        "http://localhost:11434",
        "http://localhost:4000/v1",
        {"message": {"content": "ok"}},
        True,
    )


@pytest.mark.parametrize(
    "url",
    ["http://192.0.2.10:6333", "http://169.254.169.254:6333"],
    ids=["documentation-range", "cloud-metadata"],
)
def test_the_example_config_still_refuses_other_private_hosts(
    example_settings: Settings, url: str
) -> None:
    """Verify a non-loopback private or metadata host is refused without allow_private_network."""
    with pytest.raises(SSRFBlockedError):
        QdrantClient(
            base_url=url,
            api_key="x",
            allow_private_network=example_settings.ai.allow_private_network,
        )
