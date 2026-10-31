"""Unit tests for LLMClient provider dispatches, EmbeddingRunner, and Document Chunker."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.ai import context_budget
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
    _is_json_error_payload,
    network,
    validate_base_url,
)
from devops_cli.ai.client.base import BaseLLMProviderMixin
from devops_cli.ai.client.streaming import (
    StreamFrame,
    _ollama_stream_frame,
    _read_event_stream,
)
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import (
    NDJSON,
    OPENAI_DONE,
    anthropic_stream_frames,
    ollama_line,
    openai_chunk,
    reply,
    route_client,
    route_llm_clients,
    streamed,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

pytestmark = pytest.mark.usefixtures("keyring_store")


def _quiet_stream_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a stream's spend estimate off the tokenizer and the ledger, neither under test."""
    monkeypatch.setattr(context_budget, "count_tokens", lambda text, *args, **kwargs: len(text))
    monkeypatch.setattr("devops_cli.ai.spend.track_request_spend", lambda **kwargs: None)


def _sse_event(data: str) -> httpx2.ServerSentEvent:
    return httpx2.ServerSentEvent(data=data)


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
    route_client(client, monkeypatch, lambda request: mock_resp)

    res = client.chat(system="sys", user="user")
    assert "Ollama response" in str(res)


def test_llm_client_context_window_and_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_payloads: list[dict[str, Any]] = []

    def answer(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/api/chat"):
            captured_payloads.append(json.loads(request.content))
        return _make_resp(200, {"message": {"content": "OK"}})

    route_llm_clients(monkeypatch, answer)

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
    route_client(client, monkeypatch, lambda request: mock_resp)

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
    route_client(client, monkeypatch, lambda request: mock_resp)

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
    route_client(client, monkeypatch, lambda request: mock_resp)

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
    """Test stream frame parsers for Ollama, Claude, and OpenAI, and the error payload check."""
    # 1. Ollama frames
    assert (
        _ollama_stream_frame('{"message": {"content": "hello"}}'),
        _ollama_stream_frame('{"message": {"thinking": "pondering"}}'),
        _ollama_stream_frame(""),
        _ollama_stream_frame("invalid json"),
    ) == (
        StreamFrame(chunk="hello"),
        StreamFrame(chunk="<think>pondering</think>"),
        StreamFrame(),
        StreamFrame(),
    )

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

    # Test list_models, then preload
    tags = {"models": [{"name": "llama3:latest"}, {"name": "qwen2.5:latest"}]}
    route_client(
        client,
        monkeypatch,
        lambda request: _make_resp(
            200, tags if request.url.path == "/api/tags" else {"response": ""}
        ),
    )
    models = client.list_models()
    assert "llama3:latest" in models

    pre_res = client.preload_models()
    assert len(pre_res) == 2
    assert all(pre_res.values())

    # Test non-blocking preload with callback, waiting for it so it ends inside the test, while
    # the routed client still answers it
    called: list[dict[str, bool]] = []
    finished = threading.Event()

    def on_complete(results: dict[str, bool]) -> None:
        called.append(results)
        finished.set()

    client.preload_models(blocking=False, on_complete=on_complete)
    assert finished.wait(THREAD_HANDOFF_BOUND_SECONDS)
    assert called == [pre_res]


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

    # 3. Stream max bytes exceeded
    with (
        streamed([b"data: huge line of stream tokens\n\n"] * 100) as response,
        pytest.raises(AIClientError, match="exceeded maximum stream size"),
    ):
        list(
            _read_event_stream(
                response, lambda ev: StreamFrame(chunk=ev.data), "TestProvider", max_stream_bytes=50
            )
        )

    # 4. Ollama semaphore and active tracking
    with client._track_ollama_url("http://localhost:11434", max_parallel=2):
        assert network.active_ollama_requests.get("http://localhost:11434", 0) >= 1

    # 5. Stream dispatch for Claude and OpenAI
    claude_cfg = AIConfig(
        provider="claude",
        model="claude-sonnet-4-5",
        api_key="sk-ant-test",
        allow_private_network=True,
    )
    claude_client = LLMClient(claude_cfg)
    _quiet_stream_spend(monkeypatch)
    claude_frames = anthropic_stream_frames(["hello ", "world"])

    def _claude_stream_handler(request: httpx2.Request) -> httpx2.Response:
        if "models" in request.url.path:
            return httpx2.Response(404, json={"error": "not found"})
        return reply(claude_frames)

    route_client(claude_client, monkeypatch, _claude_stream_handler)
    assert "".join(claude_client.chat_stream("system", "user")) == "hello world"

    # 6. OpenAI models listing
    openai_cfg = AIConfig(
        provider="openai",
        model="gpt-4o",
        api_key="sk-test",
        allow_private_network=True,
    )
    openai_client = LLMClient(openai_cfg)
    openai_replies = {
        "/models": {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]},
        "/chat/completions": {
            "choices": [{"message": {"role": "assistant", "content": "Connected and healthy"}}],
            "usage": {"total_tokens": 12},
        },
    }
    route_client(
        openai_client,
        monkeypatch,
        lambda request: _make_resp(200, openai_replies[request.url.path.removeprefix("/v1")]),
    )
    models = openai_client.list_models()
    assert "gpt-4o" in models

    # 7. chat_messages
    from devops_cli.models.ai import ChatMessage

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
        server="http://example.com:11434",
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
        server="http://example.com:11435",
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
        server="http://example.com:11434",
        models_evaluated_count=1,
        avg_latency_p50_ms=12.5,
        avg_throughput_items_per_sec=80.0,
        fastest_model="model-a",
        top_score_model="model-a",
    )
    srv_2 = EmbeddingServerSummary(
        server="http://example.com:11435",
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
    route_client(ollama_client, monkeypatch, lambda request: mock_chat_resp)

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
    route_client(claude_client, monkeypatch, lambda request: mock_claude_msg_resp)

    claude_out = claude_client.chat_messages(
        "System prompt instructions",
        [ChatMessage(role="user", content="Analyze this architecture")],
    )
    assert "Claude message response" in str(claude_out)


def test_base_provider_mixin_abstract_methods() -> None:
    mixin = BaseLLMProviderMixin()
    with pytest.raises(NotImplementedError) as raised:
        _ = mixin.backend_type
    assert raised.value is not None
    with pytest.raises(NotImplementedError) as raised:
        _ = mixin.backend_host
    assert raised.value is not None
    with pytest.raises(NotImplementedError) as raised:
        mixin._validate_base_url("http://example.com")
    assert raised.value is not None
    with pytest.raises(NotImplementedError) as raised:
        mixin._request_timeout()
    assert raised.value is not None
    with pytest.raises(NotImplementedError) as raised:
        mixin._connection_error(RuntimeError("err"))
    assert raised.value is not None
    with pytest.raises(NotImplementedError) as raised:
        mixin._strip_think_blocks("test")
    assert raised.value is not None
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
    assert validate_base_url("http://localhost:11434/") == "http://localhost:11434"


def test_streaming_extractors_edge_cases() -> None:
    assert (
        _ollama_stream_frame(""),
        _ollama_stream_frame("invalid json"),
        _ollama_stream_frame('{"message": {"thinking": "reasoning"}}'),
        _ollama_stream_frame('{"message": {"content": "token"}}'),
    ) == (
        StreamFrame(),
        StreamFrame(),
        StreamFrame(chunk="<think>reasoning</think>"),
        StreamFrame(chunk="token"),
    )


def test_ollama_streaming_and_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434", "http://localhost:11435"],
        allow_private_network=True,
    )
    client_ollama = LLMClient(ollama_cfg)
    _quiet_stream_spend(monkeypatch)
    ollama_frames = [ollama_line("Ollama "), ollama_line("stream", done=True)]

    # 1. Successful stream
    route_client(client_ollama, monkeypatch, lambda request: reply(ollama_frames, NDJSON))
    tokens = list(client_ollama.chat_stream("system", "prompt"))
    assert "".join(tokens) == "Ollama stream"

    # 2. Failover on connection error
    def failover_stream(request: httpx2.Request) -> httpx2.Response:
        if len(failover_sent) == 1:
            raise httpx2.ConnectError("Server 1 down", request=request)
        return reply(ollama_frames, NDJSON)

    failover_sent = route_client(client_ollama, monkeypatch, failover_stream)
    tokens_failover = list(client_ollama.chat_stream("system", "prompt"))
    assert ("".join(tokens_failover), len(failover_sent)) == ("Ollama stream", 2)

    # 3. Failover on HTTP 404 model not found (streaming)
    def not_found_stream(request: httpx2.Request) -> httpx2.Response:
        if len(not_found_sent) == 1:
            return httpx2.Response(404, text='{"error":"model \'llama3\' not found"}')
        return reply(ollama_frames, NDJSON)

    not_found_sent = route_client(client_ollama, monkeypatch, not_found_stream)
    tokens_404 = list(client_ollama.chat_stream("system", "prompt"))
    assert ("".join(tokens_404), len(not_found_sent)) == ("Ollama stream", 2)

    # 4. Failover on HTTP 404 model not found (non-streaming)
    def not_found_chat(request: httpx2.Request) -> httpx2.Response:
        if len(not_found_chat_sent) == 1:
            return httpx2.Response(404, text='{"error":"model \'llama3\' not found"}')
        return _make_resp(200, {"message": {"content": "Ollama failover success"}})

    not_found_chat_sent = route_client(client_ollama, monkeypatch, not_found_chat)
    res_non_stream = client_ollama.chat(system="system", user="prompt")
    assert ("Ollama failover success" in str(res_non_stream), len(not_found_chat_sent)) == (
        True,
        2,
    )


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
    _quiet_stream_spend(monkeypatch)
    copilot_frames = [openai_chunk("Copilot "), openai_chunk("stream"), OPENAI_DONE]
    route_client(client_copilot, monkeypatch, lambda request: reply(copilot_frames))
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

    route_client(
        client_openai,
        monkeypatch,
        lambda request: httpx2.Response(401, json={"error": {"message": "Invalid API key"}}),
    )
    with pytest.raises(AIClientError) as raised:
        client_openai.chat("sys", "user")
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"

    # 3. Stream connection error
    def mock_stream_err(*args: Any, **kwargs: Any) -> Any:
        raise httpx2.ConnectError("Connection refused")

    monkeypatch.setattr(httpx2.Client, "stream", mock_stream_err)
    with pytest.raises(AIClientError) as raised:
        list(client_openai.chat_stream("sys", "user"))
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"


def test_claude_streaming_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    claude_cfg = AIConfig(
        provider="claude",
        model="claude-sonnet-4-5",
        api_key="sk-ant-test",
        allow_private_network=True,
    )
    client_claude = LLMClient(claude_cfg)
    _quiet_stream_spend(monkeypatch)

    # 1. Streaming
    claude_frames = anthropic_stream_frames(["Claude ", "stream"])

    def _claude_handler(request: httpx2.Request) -> httpx2.Response:
        if "models" in request.url.path:
            return httpx2.Response(404, json={"error": "not found"})
        return reply(claude_frames)

    route_client(client_claude, monkeypatch, _claude_handler)
    tokens = list(client_claude.chat_stream("system", "prompt"))
    assert "".join(tokens) == "Claude stream"

    # 2. Error handling
    route_client(
        client_claude,
        monkeypatch,
        lambda request: httpx2.Response(400, json={"error": {"message": "invalid_request_error"}}),
    )
    with pytest.raises(AIClientError) as raised:
        client_claude.chat("sys", "user")
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"


def test_openai_and_ollama_list_models(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. OpenAI list models
    openai_cfg = AIConfig(
        provider="openai", model="gpt-4o", api_key="test-key", allow_private_network=True
    )
    client_openai = LLMClient(openai_cfg)

    def listing(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/models"):
            return httpx2.Response(200, json={"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]})
        if request.url.path == "/api/tags":
            return httpx2.Response(
                200, json={"models": [{"name": "llama3:latest"}, {"name": "qwen2.5:latest"}]}
            )
        return httpx2.Response(404)

    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    route_client(client_openai, monkeypatch, listing)
    models = client_openai.list_models()
    assert models == ["gpt-4o", "gpt-4o-mini"]

    # 2. OpenAI list models connection error
    route_client(client_openai, monkeypatch, refuse)
    with pytest.raises(AIClientError) as raised:
        client_openai.list_models()
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"

    # 3. Ollama list models
    ollama_cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client_ollama = LLMClient(ollama_cfg)
    route_client(client_ollama, monkeypatch, listing)
    ollama_models = client_ollama.list_models()
    assert ollama_models == ["llama3:latest", "qwen2.5:latest"]

    # 4. Ollama list models error
    route_client(client_ollama, monkeypatch, refuse)
    with pytest.raises(AIClientError) as raised:
        client_ollama.list_models()
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"


def test_chat_cache_and_starting_point(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_cfg = AIConfig(
        provider="ollama",
        model="llama3",
        ollama_urls=["http://localhost:11434"],
        allow_private_network=True,
    )
    client = LLMClient(ollama_cfg, cache_enabled=True)
    route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(200, json={"message": {"content": "Cached output"}}),
    )

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
    route_client(client, monkeypatch, lambda request: mock_resp)
    res = client.chat("sys", "user", enable_thinking=True)
    assert res.thinking == "reasoning steps"
    assert res.processing_seconds == 4.0

    # 2. HTTP error in ollama request
    route_client(client, monkeypatch, lambda request: httpx2.Response(500))
    with pytest.raises(AIClientError) as raised:
        client.chat("sys", "user_error", use_cache=False)
    assert raised.value.error_code == "LLM_INFERENCE_ERROR"


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
    route_client(client, monkeypatch, lambda request: mock_resp)

    res = client.chat_messages(
        system="sys",
        messages=[ChatMessage(role="user", content="Draft report")],
        starting_point="Previous draft content",
        use_cache=False,
    )
    assert str(res) == "Augmented response"


def test_openai_default_routes_use_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    openai_cfg = AIConfig(
        provider="openai", model="gpt-4o", api_key="test-key", allow_private_network=True
    )
    client_openai = LLMClient(openai_cfg)

    def answer(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/models"):
            return httpx2.Response(200, json={"data": [{"id": "gpt-4o"}]})
        body_text = request.read().decode()
        if "stream" in body_text:
            return reply([openai_chunk("hello"), OPENAI_DONE])
        return httpx2.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    sent = route_client(client_openai, monkeypatch, answer)
    client_openai.chat("sys", "hello")
    list(client_openai.chat_stream("sys", "hello"))
    client_openai.list_models()

    urls = [str(r.url) for r in sent]
    assert urls == [
        "https://api.openai.com/v1/chat/completions",
        "https://api.openai.com/v1/chat/completions",
        "https://api.openai.com/v1/models",
    ]


def test_copilot_and_gateway_preserve_configured_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_copilot = LLMClient(
        AIConfig(provider="copilot", model="gpt-4o", api_key="test-key", allow_private_network=True)
    )
    client_gateway = LLMClient(
        AIConfig(
            provider="gateway",
            model="gpt-4o",
            gateway_url="https://example.com/v1",
            api_key="test-key",
            allow_private_network=True,
        )
    )

    def answer(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    sent_copilot = route_client(client_copilot, monkeypatch, answer)
    client_copilot.chat("sys", "hello")
    assert [str(r.url) for r in sent_copilot] == ["https://api.githubcopilot.com/chat/completions"]

    sent_gateway = route_client(client_gateway, monkeypatch, answer)
    client_gateway.chat("sys", "hello")
    assert [str(r.url) for r in sent_gateway] == ["https://example.com/v1/chat/completions"]


def test_openai_sdk_client_uses_factory_transport() -> None:
    client = LLMClient(
        AIConfig(provider="openai", model="gpt-4o", api_key="test-key", allow_private_network=True)
    )
    sdk_client = client._openai_client()
    assert sdk_client._client is client._shared_client()


def test_backend_type_resolves_without_mock_fallback() -> None:
    """Verify backend_type never returns 'mock' when provider is not a string."""
    cfg = AIConfig(model="test-model")
    object.__setattr__(cfg, "provider", None)
    client = LLMClient(cfg)
    assert client.backend_type == "ollama"
