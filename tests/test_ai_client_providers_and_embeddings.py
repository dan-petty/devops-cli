"""Unit tests for LLMClient provider dispatches, EmbeddingRunner, and Document Chunker."""

from __future__ import annotations

import httpx2
import pytest

from devops_cli.ai.benchmark.document_chunker import (
    InMemoryDocumentTokenizer,
    load_test_document_corpus,
)
from devops_cli.ai.benchmark.embedding_runner import (
    compute_ndcg_at_k,
    cosine_similarity,
)
from devops_cli.ai.client import LLMClient
from devops_cli.config.settings import AIConfig


@pytest.fixture(autouse=True)
def _bypass_dns_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devops_cli.core.validation.validate_service_url", lambda *args, **kwargs: None
    )


def _make_resp(status_code: int = 200, json_data: dict | None = None) -> httpx2.Response:
    req = httpx2.Request("POST", "http://localhost")
    return httpx2.Response(status_code, request=req, json=json_data)


def test_llm_client_ollama_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(cfg)

    mock_resp = _make_resp(
        200,
        {
            "message": {"content": "Ollama response"},
            "prompt_eval_count": 10,
            "eval_count": 20,
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_resp)

    res = client.chat(system="sys", user="user")
    assert "Ollama response" in str(res)


def test_llm_client_claude_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AIConfig(
        provider="claude",
        model="claude-3-5-sonnet",
        api_key="sk-ant-test",
        allow_private_network=True,
    )
    client = LLMClient(cfg)

    mock_resp = _make_resp(
        200,
        {
            "content": [{"type": "text", "text": "Anthropic response"}],
            "usage": {"input_tokens": 15, "output_tokens": 25},
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_resp)

    res = client.chat(system="sys", user="user")
    assert "Anthropic response" in str(res)


def test_llm_client_openai_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AIConfig(provider="openai", model="gpt-4o", api_key="sk-test", allow_private_network=True)
    client = LLMClient(cfg)

    mock_resp = _make_resp(
        200,
        {
            "choices": [{"message": {"content": "OpenAI response"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 18},
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_resp)

    res = client.chat(system="sys", user="user")
    assert "OpenAI response" in str(res)


def test_llm_client_copilot_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AIConfig(
        provider="copilot", model="gpt-4o", api_key="ghp-test", allow_private_network=True
    )
    client = LLMClient(cfg)

    mock_resp = _make_resp(
        200,
        {
            "choices": [{"message": {"content": "Copilot response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_resp)

    res = client.chat(system="sys", user="user")
    assert "Copilot response" in str(res)


def test_document_tokenizer_and_chunker() -> None:
    tok = InMemoryDocumentTokenizer()
    text = "## Heading 1\nHello world, this is an automated test with enough words."
    chunks = tok.tokenize_and_chunk(text)
    assert len(chunks) > 0

    corpus = load_test_document_corpus()
    assert len(corpus) > 0


def test_embedding_runner_similarity_and_ndcg() -> None:
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert cosine_similarity(v1, v2) == pytest.approx(1.0)
    assert cosine_similarity(v1, v3) == pytest.approx(0.0)

    ranked = ["doc1", "doc2", "doc3"]
    relevant = {"doc1", "doc3"}
    ndcg = compute_ndcg_at_k(ranked, relevant, k=3)
    assert 0.0 <= ndcg <= 1.0
