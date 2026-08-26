"""Unit tests for LLMClient provider dispatches, EmbeddingRunner, and Document Chunker."""

from __future__ import annotations

from pathlib import Path

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


def test_chunk_extractors_and_stream_helpers() -> None:
    """Test chunk extractor functions for Ollama, Claude, and OpenAI."""
    from devops_cli.ai.client import (
        _extract_claude_stream_chunk,
        _extract_ollama_stream_chunk,
        _extract_openai_stream_chunk,
        _is_json_error_payload,
    )

    # 1. Ollama chunk extraction
    assert _extract_ollama_stream_chunk('{"message": {"content": "hello"}}') == "hello"
    assert (
        _extract_ollama_stream_chunk('{"message": {"thinking": "pondering"}}')
        == "<think>pondering</think>"
    )
    assert _extract_ollama_stream_chunk("") is None
    assert _extract_ollama_stream_chunk("invalid json") is None

    # 2. Claude chunk extraction
    c_chunk, c_done = _extract_claude_stream_chunk(
        'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "claude text"}}'
    )
    assert c_chunk == "claude text"
    assert c_done is False

    _, c_done_true = _extract_claude_stream_chunk("data: [DONE]")
    assert c_done_true is True

    # 3. OpenAI chunk extraction
    o_chunk, o_done = _extract_openai_stream_chunk(
        'data: {"choices": [{"delta": {"content": "openai text"}}]}'
    )
    assert o_chunk == "openai text"
    assert o_done is False

    _, o_done_true = _extract_openai_stream_chunk("data: [DONE]")
    assert o_done_true is True

    # 4. JSON error payload detector
    assert _is_json_error_payload('{"error": "model not found"}') is True
    assert _is_json_error_payload('{"error_code": 404}') is True
    assert _is_json_error_payload('{"response": "all good"}') is False
    assert _is_json_error_payload("plain text") is False


def test_llm_client_properties_and_list_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test LLMClient backend properties, model listing, round robin, and prewarming."""
    cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434", "http://localhost:11435"],
        allow_private_network=True,
    )
    client = LLMClient(cfg)

    assert client.backend_type == "ollama"
    assert "11434" in client.backend_host
    assert "ollama" in client.backend_info

    # Test round robin index
    idx1 = LLMClient._load_and_increment_rr_index(2)
    idx2 = LLMClient._load_and_increment_rr_index(2)
    assert (idx1 + 1) % 2 == idx2

    # Test list_models
    mock_tags = _make_resp(200, {"models": [{"name": "llama3:latest"}, {"name": "qwen2.5:latest"}]})
    monkeypatch.setattr(httpx2.Client, "get", lambda self, url, **kwargs: mock_tags)
    models = client.list_models()
    assert "llama3:latest" in models

    # Test preload
    mock_gen = _make_resp(200, {"response": ""})
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_gen)
    pre_res = client.preload_models()
    assert len(pre_res) == 2
    assert all(pre_res.values())

    # Test non-blocking preload with callback
    called = []
    client.preload_models(blocking=False, on_complete=lambda r: called.append(r))


def test_llm_client_streaming_and_error_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test streaming chunk processing, thinking fallback, limits, and error mappings."""
    from devops_cli.ai.client import AIClientError, _consume_streaming_lines

    cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(cfg)

    # 1. Connection error messages per provider
    assert "Ollama" in str(client._connection_error(Exception("down")))
    client._config.provider = "claude"
    assert "Claude" in str(client._connection_error(Exception("down")))
    client._config.provider = "openai"
    assert "AI provider" in str(client._connection_error(Exception("down")))
    client._config.provider = "ollama"

    # 2. Base URL validation
    with pytest.raises(AIClientError, match="Missing"):
        client._validate_base_url("")
    with pytest.raises(AIClientError, match="scheme"):
        client._validate_base_url("ftp://example.com")
    with pytest.raises(AIClientError, match="hostname"):
        client._validate_base_url("http://")

    # 3. Read limited JSON
    mock_big_header = httpx2.Response(200, headers={"content-length": "50000000"}, content=b"{}")
    with pytest.raises(AIClientError, match="exceeded maximum size"):
        client._read_limited_json(mock_big_header, limit_bytes=100)

    mock_bad_json = httpx2.Response(200, content=b"invalid json")
    with pytest.raises(AIClientError, match="Invalid JSON response"):
        client._read_limited_json(mock_bad_json)

    # 4. Stream max bytes exceeded
    class DummyStreamResp:
        def iter_lines(self):
            for _ in range(100):
                yield "data: huge line of stream tokens"

    with pytest.raises(AIClientError, match="exceeded maximum stream size"):
        gen = _consume_streaming_lines(
            DummyStreamResp(),  # type: ignore[arg-type]
            lambda line: (line, False),
            "TestProvider",
        )
        # Force low limit by setting MAX_STREAM_BYTES temporarily
        monkeypatch.setattr("devops_cli.ai.client.MAX_STREAM_BYTES", 50)
        list(gen)

    # 5. Ollama semaphore and active tracking
    with client._track_ollama_url("http://localhost:11434", max_parallel=2):
        assert client._active_ollama_requests.get("http://localhost:11434", 0) >= 1

    # 6. Stream dispatch for Claude and OpenAI
    claude_cfg = AIConfig(
        provider="claude",
        model="claude-3-5-sonnet",
        api_key="sk-ant-test",
        allow_private_network=True,
    )
    claude_client = LLMClient(claude_cfg)

    class MockStreamContext:
        def __init__(self, lines):
            self._lines = lines
            self.status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_lines(self):
            yield from self._lines

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        httpx2.Client,
        "stream",
        lambda self, method, url, **kwargs: MockStreamContext(
            [
                'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello "}}',
                'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "world"}}',
                "data: [DONE]",
            ]
        ),
    )
    streamed = list(claude_client.chat_stream("system", "user"))
    assert "".join(streamed) == "hello world"

    # 7. OpenAI models listing
    openai_cfg = AIConfig(
        provider="openai",
        model="gpt-4o",
        api_key="sk-test",
        allow_private_network=True,
    )
    openai_client = LLMClient(openai_cfg)
    mock_models_resp = _make_resp(200, {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]})
    monkeypatch.setattr(httpx2.Client, "get", lambda self, url, **kwargs: mock_models_resp)
    models = openai_client.list_models()
    assert "gpt-4o" in models

    # 8. chat_messages
    from devops_cli.models.ai import ChatMessage

    mock_chat_resp = _make_resp(
        200,
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Connected and healthy",
                    }
                }
            ],
            "usage": {"total_tokens": 12},
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_chat_resp)

    chat_out = openai_client.chat_messages(
        "System prompt",
        [ChatMessage(role="user", content="Ping")],
    )
    assert "Connected and healthy" in str(chat_out)


def test_embedding_runner_report_rendering_and_markdown(tmp_path: Path) -> None:
    """Verify EmbeddingBenchmarkRunner report generation in Table, JSON, and Markdown formats."""
    from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkRunner
    from devops_cli.models.benchmark import (
        EmbeddingBenchmarkReport,
        EmbeddingBenchmarkResult,
        EmbeddingServerSummary,
    )

    runner = EmbeddingBenchmarkRunner(models=["model-a", "model-b"], is_dry_run=True)

    res_a = EmbeddingBenchmarkResult(
        model="model-a",
        server="http://node1:11434",
        dimension=768,
        recall_at_1=90.0,
        recall_at_3=95.0,
        mrr=0.92,
        ndcg_at_5=0.94,
        mean_cosine_margin=0.45,
        latency_ms_p50=12.5,
        throughput_items_per_sec=80.0,
        overall_score=92.5,
        category_accuracies={"security": 95.0, "kubernetes": 90.0},
    )
    res_b = EmbeddingBenchmarkResult(
        model="model-b",
        server="http://node2:11434",
        dimension=1536,
        recall_at_1=85.0,
        recall_at_3=90.0,
        mrr=0.88,
        ndcg_at_5=0.90,
        mean_cosine_margin=0.40,
        latency_ms_p50=18.0,
        throughput_items_per_sec=55.0,
        overall_score=87.0,
        category_accuracies={"security": 85.0, "kubernetes": 89.0},
    )

    srv_1 = EmbeddingServerSummary(
        server="http://node1:11434",
        models_evaluated_count=1,
        avg_latency_p50_ms=12.5,
        avg_throughput_items_per_sec=80.0,
        fastest_model="model-a",
        top_score_model="model-a",
    )
    srv_2 = EmbeddingServerSummary(
        server="http://node2:11434",
        models_evaluated_count=1,
        avg_latency_p50_ms=18.0,
        avg_throughput_items_per_sec=55.0,
        fastest_model="model-b",
        top_score_model="model-b",
    )

    report = EmbeddingBenchmarkReport(
        session_id="20260826-emb-test",
        models=[res_a, res_b],
        server_benchmarks=[srv_1, srv_2],
        recommendations=["Model A is recommended for production RAG retrieval."],
    )

    # 1. Markdown generation
    md = runner.generate_markdown(report)
    assert "# Embedding Model Benchmark Report" in md
    assert "Leaderboard Summary" in md
    assert "model-a" in md

    # 2. Print report table, markdown, json
    runner.print_report(report, format_type="table")
    runner.print_report(report, format_type="markdown")
    runner.print_report(report, format_type="json")

    # 3. Save report
    runner._save_report(report)
    assert runner.is_dry_run_active is True


def test_llm_client_embeddings_and_claude_messages(monkeypatch) -> None:
    """Verify LLMClient Ollama and Claude chat_messages formatting and responses."""
    from devops_cli.models.ai import ChatMessage

    # 1. Ollama chat_messages
    ollama_cfg = AIConfig(
        provider="ollama",
        model="qwen2.5-coder:14b",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    ollama_client = LLMClient(ollama_cfg)

    mock_chat_resp = _make_resp(
        200,
        {
            "message": {"role": "assistant", "content": "Ollama response"},
            "prompt_eval_count": 10,
            "eval_count": 20,
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_chat_resp)

    chat_out = ollama_client.chat_messages(
        "System prompt",
        [ChatMessage(role="user", content="Ping")],
    )
    assert "Ollama response" in str(chat_out)

    # 2. Claude chat_messages
    claude_cfg = AIConfig(
        provider="claude",
        model="claude-3-5-sonnet",
        api_key="sk-ant-test",
        allow_private_network=True,
    )
    claude_client = LLMClient(claude_cfg)

    mock_claude_msg_resp = _make_resp(
        200,
        {
            "content": [{"type": "text", "text": "Claude message response"}],
            "usage": {"input_tokens": 15, "output_tokens": 25},
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda self, url, **kwargs: mock_claude_msg_resp)

    claude_out = claude_client.chat_messages(
        "System prompt instructions",
        [ChatMessage(role="user", content="Analyze this architecture")],
    )
    assert "Claude message response" in str(claude_out)
