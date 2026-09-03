"""Unit tests for LLMClient provider dispatches, EmbeddingRunner, and Document Chunker."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

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
from devops_cli.ai.client import (
    AIClientError,
    LLMClient,
    LLMResponse,
    _consume_streaming_lines,
    _extract_claude_stream_chunk,
    _extract_ollama_stream_chunk,
    _extract_ollama_stream_tuple,
    _extract_openai_stream_chunk,
    _is_json_error_payload,
    model_request,
    model_request_sync,
    read_limited_json,
    validate_base_url,
)
from devops_cli.ai.client.base import BaseLLMProviderMixin
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


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


def test_llm_client_context_window_and_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_payloads: list[dict[str, Any]] = []

    def mock_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        if str(url).endswith("/api/chat") and "json" in kwargs:
            captured_payloads.append(kwargs["json"])
        return _make_resp(200, {"message": {"content": "OK"}})

    monkeypatch.setattr(httpx2.Client, "post", mock_post)

    cfg = AIConfig(
        provider="ollama",
        model="qwen2.5-coder:7b",
        ollama_urls=["http://localhost:11434"],
        context_window=40960,
        allow_private_network=True,
    )
    client = LLMClient(cfg)
    assert client.get_context_window() == 40960

    client.chat(system="sys", user="user")
    assert len(captured_payloads) == 1
    assert captured_payloads[0]["options"]["num_ctx"] == 40960


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
    from devops_cli.ai.client import AIClientError

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


@pytest.mark.asyncio
async def test_direct_model_request_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify model_request_sync and model_request direct API calls."""
    from unittest.mock import MagicMock

    from devops_cli.ai import model_request, model_request_sync
    from devops_cli.models.ai import ChatMessage

    mock_client = MagicMock()
    mock_client.chat.return_value = "Direct chat output"
    mock_client.chat_messages.return_value = "Direct chat_messages output"

    # 1. model_request_sync with string prompt
    res_sync = model_request_sync("gpt-4o", "Hello world", client=mock_client)
    assert str(res_sync) == "Direct chat output"

    # 2. model_request_sync with ChatMessage list
    res_msgs = model_request_sync(
        "gpt-4o",
        [ChatMessage(role="user", content="Test")],
        system_prompt="System",
        client=mock_client,
    )
    assert str(res_msgs) == "Direct chat_messages output"

    # 3. model_request async with string prompt
    res_async = await model_request("gpt-4o", "Async prompt", client=mock_client)
    assert str(res_async) == "Direct chat output"


def test_base_provider_mixin_abstract_methods() -> None:
    mixin = BaseLLMProviderMixin()
    with pytest.raises(NotImplementedError):
        _ = mixin.backend_type
    with pytest.raises(NotImplementedError):
        _ = mixin.backend_host
    with pytest.raises(NotImplementedError):
        mixin._validate_base_url("http://example.com")
    with pytest.raises(NotImplementedError):
        mixin._request_timeout()
    with pytest.raises(NotImplementedError):
        mixin._connection_error(RuntimeError("err"))
    with pytest.raises(NotImplementedError):
        mixin._strip_think_blocks("test")
    # Base classmethod test
    idx = BaseLLMProviderMixin._load_and_increment_rr_index(5)
    assert 0 <= idx < 5


def test_json_error_payload_and_llm_response_properties() -> None:
    assert _is_json_error_payload('{"error": "Rate limit exceeded"}') is True
    assert _is_json_error_payload('{"error_code": 429}') is True
    assert _is_json_error_payload('{"error": null}') is False
    assert _is_json_error_payload('{"error": "none"}') is False
    assert _is_json_error_payload("not json") is False
    assert _is_json_error_payload('["a", "b"]') is False

    resp = LLMResponse("content test", processing_seconds=1.2, wall_seconds=2.3)
    assert resp.text == "content test"
    assert resp.content == "content test"
    assert resp.processing_seconds == 1.2
    assert resp.wall_seconds == 2.3


def test_validate_base_url_errors() -> None:
    with pytest.raises(AIClientError, match="Missing API base URL"):
        validate_base_url("")
    with pytest.raises(AIClientError, match="Invalid API URL scheme"):
        validate_base_url("ftp://example.com")
    with pytest.raises(AIClientError, match="Missing hostname"):
        validate_base_url("http://")
    assert (
        validate_base_url("http://localhost:11434/", allow_loopback_for_local_tooling=True)
        == "http://localhost:11434"
    )


def test_read_limited_json_errors() -> None:
    req = httpx2.Request("POST", "http://example.com")
    resp_large = httpx2.Response(200, request=req, content=b"a" * 200)
    with pytest.raises(AIClientError, match="Response body exceeded maximum size"):
        read_limited_json(resp_large, limit_bytes=50)

    resp_invalid = httpx2.Response(200, request=req, content=b"not json")
    with pytest.raises(AIClientError, match="Invalid JSON response payload"):
        read_limited_json(resp_invalid)


def test_streaming_extractors_edge_cases() -> None:
    assert _extract_ollama_stream_chunk("") is None
    assert _extract_ollama_stream_chunk("invalid json") is None
    assert (
        _extract_ollama_stream_chunk('{"message": {"thinking": "reasoning"}}')
        == "<think>reasoning</think>"
    )
    assert _extract_ollama_stream_chunk('{"message": {"content": "token"}}') == "token"

    tok, done = _extract_ollama_stream_tuple('{"message": {"thinking": "th"}}')
    assert (tok, done) == ("<think>th</think>", False)
    assert _extract_ollama_stream_tuple("invalid") == (None, False)

    chunk, is_done = _extract_claude_stream_chunk("")
    assert (chunk, is_done) == (None, False)
    chunk, is_done = _extract_claude_stream_chunk("data: [DONE]")
    assert (chunk, is_done) == (None, True)
    chunk, is_done = _extract_claude_stream_chunk("data: invalid json")
    assert (chunk, is_done) == (None, False)
    chunk, is_done = _extract_claude_stream_chunk(
        'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "token"}}'
    )
    assert (chunk, is_done) == ("token", False)

    chunk, is_done = _extract_openai_stream_chunk("")
    assert (chunk, is_done) == (None, False)
    chunk, is_done = _extract_openai_stream_chunk("data: [DONE]")
    assert (chunk, is_done) == (None, True)
    chunk, is_done = _extract_openai_stream_chunk("data: invalid json")
    assert (chunk, is_done) == (None, False)
    chunk, is_done = _extract_openai_stream_chunk(
        'data: {"choices": [{"delta": {"content": "token"}}] }'
    )
    assert (chunk, is_done) == ("token", False)


def test_ollama_streaming_and_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434", "http://localhost:11435"],
        allow_private_network=True,
    )
    client_ollama = LLMClient(ollama_cfg)

    # 1. Successful stream
    class MockOllamaStreamResponse:
        status_code = 200

        def __enter__(self) -> MockOllamaStreamResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self) -> list[str]:
            return [
                '{"message": {"content": "Ollama "}, "done": false}',
                '{"message": {"content": "stream"}, "done": true}',
            ]

    monkeypatch.setattr(httpx2.Client, "stream", lambda *args, **kwargs: MockOllamaStreamResponse())
    tokens = list(client_ollama.chat_stream("system", "prompt"))
    assert "".join(tokens) == "Ollama stream"

    # 2. Failover on connection error
    call_count = 0

    def mock_failover_stream(*args: Any, **kwargs: Any) -> MockOllamaStreamResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx2.ConnectError("Server 1 down")
        return MockOllamaStreamResponse()

    monkeypatch.setattr(httpx2.Client, "stream", mock_failover_stream)
    tokens_failover = list(client_ollama.chat_stream("system", "prompt"))
    assert "".join(tokens_failover) == "Ollama stream"


def test_copilot_and_openai_streaming_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Copilot streaming with reasoning effort
    copilot_cfg = AIConfig(
        provider="github_copilot",
        model="gpt-4o",
        api_key="ghp_test_token",
        allow_private_network=True,
        reasoning_effort="high",
    )
    client_copilot = LLMClient(copilot_cfg)

    class MockCopilotStreamResponse:
        status_code = 200

        def __enter__(self) -> MockCopilotStreamResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self) -> list[str]:
            return [
                'data: {"choices": [{"delta": {"content": "Copilot "}}]}',
                'data: {"choices": [{"delta": {"content": "stream"}}]}',
                "data: [DONE]",
            ]

    monkeypatch.setattr(
        httpx2.Client, "stream", lambda *args, **kwargs: MockCopilotStreamResponse()
    )
    tokens = list(client_copilot.chat_stream("system", "prompt"))
    assert "".join(tokens) == "Copilot stream"

    # 2. OpenAI error handling
    openai_cfg = AIConfig(
        provider="openai",
        model="gpt-4o",
        api_key="sk-test",
        allow_private_network=True,
    )
    client_openai = LLMClient(openai_cfg)

    def mock_post_err(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        req = httpx2.Request("POST", url)
        return httpx2.Response(401, request=req, json={"error": {"message": "Invalid API key"}})

    monkeypatch.setattr(httpx2.Client, "post", mock_post_err)
    with pytest.raises(AIClientError):
        client_openai.chat("sys", "user")

    # 3. Stream connection error
    def mock_stream_err(*args: Any, **kwargs: Any) -> Any:
        raise httpx2.ConnectError("Connection refused")

    monkeypatch.setattr(httpx2.Client, "stream", mock_stream_err)
    with pytest.raises(AIClientError):
        list(client_openai.chat_stream("sys", "user"))


def test_claude_streaming_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    claude_cfg = AIConfig(
        provider="claude",
        model="claude-3-5-sonnet",
        api_key="sk-ant-test",
        allow_private_network=True,
    )
    client_claude = LLMClient(claude_cfg)

    # 1. Streaming
    class MockClaudeStreamResponse:
        status_code = 200

        def __enter__(self) -> MockClaudeStreamResponse:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self) -> list[str]:
            return [
                'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Claude "}}',
                'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "stream"}}',
                "data: [DONE]",
            ]

    monkeypatch.setattr(httpx2.Client, "stream", lambda *args, **kwargs: MockClaudeStreamResponse())
    tokens = list(client_claude.chat_stream("system", "prompt"))
    assert "".join(tokens) == "Claude stream"

    # 2. Error handling
    def mock_claude_err(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        req = httpx2.Request("POST", url)
        return httpx2.Response(
            400, request=req, json={"error": {"message": "invalid_request_error"}}
        )

    monkeypatch.setattr(httpx2.Client, "post", mock_claude_err)
    with pytest.raises(AIClientError):
        client_claude.chat("sys", "user")


def test_openai_and_ollama_list_models(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. OpenAI list models
    openai_cfg = AIConfig(
        provider="openai", model="gpt-4o", api_key="test-key", allow_private_network=True
    )
    client_openai = LLMClient(openai_cfg)

    def mock_get(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        req = httpx2.Request("GET", url)
        if "/models" in url:
            return httpx2.Response(
                200, request=req, json={"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
            )
        if "/api/tags" in url:
            return httpx2.Response(
                200,
                request=req,
                json={"models": [{"name": "llama3:latest"}, {"name": "qwen2.5:latest"}]},
            )
        return httpx2.Response(404, request=req)

    monkeypatch.setattr(httpx2.Client, "get", mock_get)
    models = client_openai.list_models()
    assert models == ["gpt-4o", "gpt-4o-mini"]

    # 2. OpenAI list models connection error
    def mock_openai_get_err(*args: Any, **kwargs: Any) -> httpx2.Response:
        raise httpx2.ConnectError("OpenAI down")

    monkeypatch.setattr(httpx2.Client, "get", mock_openai_get_err)
    with pytest.raises(AIClientError):
        client_openai.list_models()

    # 3. Ollama list models
    ollama_cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client_ollama = LLMClient(ollama_cfg)
    monkeypatch.setattr(httpx2.Client, "get", mock_get)
    ollama_models = client_ollama.list_models()
    assert ollama_models == ["llama3:latest", "qwen2.5:latest"]

    # 4. Ollama list models error
    def mock_get_err(*args: Any, **kwargs: Any) -> httpx2.Response:
        raise httpx2.ConnectError("Ollama down")

    monkeypatch.setattr(httpx2.Client, "get", mock_get_err)
    with pytest.raises(AIClientError):
        client_ollama.list_models()


def test_chat_cache_and_starting_point(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(ollama_cfg, cache_enabled=True)

    def mock_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        req = httpx2.Request("POST", url)
        return httpx2.Response(200, request=req, json={"message": {"content": "Cached output"}})

    monkeypatch.setattr(httpx2.Client, "post", mock_post)

    # First call primes cache
    res1 = client.chat_messages(
        system="sys",
        messages=[ChatMessage(role="user", content="user1")],
        use_cache=True,
        append_cache=False,
    )
    assert str(res1) == "Cached output"

    # Second call hits cache
    res2 = client.chat_messages(
        system="sys",
        messages=[ChatMessage(role="user", content="user1")],
        use_cache=True,
        append_cache=False,
    )
    assert res2.cached is True


def test_direct_model_request_sync_and_async(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        req = httpx2.Request("POST", url)
        return httpx2.Response(200, request=req, json={"message": {"content": "Direct reply"}})

    monkeypatch.setattr(httpx2.Client, "post", mock_post)

    res1 = model_request_sync("llama3", "Hello direct")
    assert "Direct reply" in str(res1)

    res2 = asyncio.run(model_request("llama3", [ChatMessage(role="user", content="Hello async")]))
    assert "Direct reply" in str(res2)


def test_ollama_thinking_only_and_total_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
        reasoning_effort="medium",
    )
    client = LLMClient(ollama_cfg)

    # 1. Thinking only and total duration
    mock_resp = httpx2.Response(
        200,
        request=httpx2.Request("POST", "http://localhost:11434/api/chat"),
        json={
            "message": {"thinking": "reasoning steps"},
            "total_duration": 5000000000,
            "load_duration": 1000000000,
        },
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda *args, **kwargs: mock_resp)
    res = client.chat("sys", "user", enable_thinking=True)
    assert res.thinking == "reasoning steps"
    assert res.processing_seconds == 4.0

    # 2. HTTP error in ollama request
    def mock_err_post(*args: Any, **kwargs: Any) -> httpx2.Response:
        req = httpx2.Request("POST", "http://localhost:11434/api/chat")
        resp = httpx2.Response(500, request=req)
        resp.raise_for_status()
        return resp

    monkeypatch.setattr(httpx2.Client, "post", mock_err_post)
    with pytest.raises(AIClientError):
        client.chat("sys", "user_error", use_cache=False)


def test_augment_messages_starting_point(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(ollama_cfg)
    mock_resp = httpx2.Response(
        200,
        request=httpx2.Request("POST", "http://localhost"),
        json={"message": {"content": "Augmented response"}},
    )
    monkeypatch.setattr(httpx2.Client, "post", lambda *args, **kwargs: mock_resp)

    res = client.chat_messages(
        system="sys",
        messages=[ChatMessage(role="user", content="Draft report")],
        starting_point="Previous draft content",
        use_cache=False,
    )
    assert str(res) == "Augmented response"
