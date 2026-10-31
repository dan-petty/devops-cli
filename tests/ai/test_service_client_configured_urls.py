"""Tests verifying service clients use only configured URLs (#1165)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.config.settings import AIConfig, reset_settings_cache
from devops_cli.exceptions import ConfigurationError
from devops_cli.main import app
from tests.llm_stream_fakes import as_requested

pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner()


def test_resolve_ai_endpoint_gateway_success() -> None:
    """Gateway provider resolves configured gateway URL and model aliases."""
    from devops_cli.ai.endpoints import resolve_ai_endpoint

    cfg = AIConfig(provider="gateway", gateway_url="https://gateway.example.com/v1")
    resolved = resolve_ai_endpoint(cfg)
    assert resolved.provider == "gateway"
    assert resolved.urls == ("https://gateway.example.com/v1",)
    assert "devops-coder" in resolved.models
    assert "devops-embedding" in resolved.models


def test_resolve_ai_endpoint_gateway_unconfigured_raises() -> None:
    """Gateway provider without gateway URL raises ConfigurationError naming ai.gateway_url."""
    from devops_cli.ai.endpoints import resolve_ai_endpoint

    cfg = AIConfig(provider="gateway", gateway_url=None)
    with pytest.raises(ConfigurationError) as exc_info:
        resolve_ai_endpoint(cfg)
    assert exc_info.value.key == "ai.gateway_url"


def test_resolve_ai_endpoint_ollama_success() -> None:
    """Ollama provider resolves configured Ollama URLs."""
    from devops_cli.ai.endpoints import resolve_ai_endpoint

    cfg = AIConfig(provider="ollama", ollama_urls=["http://node1.example.com:11434"])
    resolved = resolve_ai_endpoint(cfg)
    assert resolved.provider == "ollama"
    assert resolved.urls == ("http://node1.example.com:11434",)


def test_resolve_ai_endpoint_ollama_unconfigured_raises() -> None:
    """Ollama provider without ollama_urls raises ConfigurationError naming ai.ollama_urls."""
    from devops_cli.ai.endpoints import resolve_ai_endpoint

    cfg = AIConfig(provider="ollama", ollama_urls=[])
    with pytest.raises(ConfigurationError) as exc_info:
        resolve_ai_endpoint(cfg)
    assert exc_info.value.key == "ai.ollama_urls"


def test_ai_test_unconfigured_exits_nonzero_and_names_setting(
    isolate_devops_cli_config: Any,
) -> None:
    """devops ai test without configured Ollama URLs exits non-zero and names ai.ollama_urls."""
    isolate_devops_cli_config.write_text(
        "ai:\n  provider: ollama\n  ollama_urls: []\n", encoding="utf-8"
    )
    reset_settings_cache()
    result = runner.invoke(app, ["ai", "test"])
    assert result.exit_code != 0
    assert "ai.ollama_urls" in result.output or "ollama_urls" in result.output


def test_rag_query_unconfigured_exits_nonzero_and_names_setting(
    isolate_devops_cli_config: Any,
) -> None:
    """devops ai rag query without configured qdrant.url exits non-zero and names qdrant.url."""
    isolate_devops_cli_config.write_text("qdrant:\n  url: null\n", encoding="utf-8")
    reset_settings_cache()
    result = runner.invoke(app, ["ai", "rag", "query", "search text"])
    assert result.exit_code != 0
    assert "qdrant.url" in result.output


def test_ai_benchmark_embedding_unconfigured_exits_nonzero_and_names_setting(
    isolate_devops_cli_config: Any,
) -> None:
    """devops ai benchmark --type embedding without configured URLs exits non-zero."""
    isolate_devops_cli_config.write_text(
        "ai:\n  provider: ollama\n  ollama_urls: []\n", encoding="utf-8"
    )
    reset_settings_cache()
    result = runner.invoke(app, ["ai", "benchmark", "--type", "embedding"])
    assert result.exit_code != 0
    assert "ai.ollama_urls" in result.output or "ollama_urls" in result.output


def test_review_path_unconfigured_exits_nonzero_and_names_setting(
    isolate_devops_cli_config: Any,
) -> None:
    """devops review path without configured URLs exits non-zero and names ai.ollama_urls."""
    scratch_dir = Path(".data/agent/scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    test_file = scratch_dir / "test_review_sample.py"
    test_file.write_text("print('test')\n", encoding="utf-8")
    try:
        isolate_devops_cli_config.write_text(
            "ai:\n  provider: ollama\n  ollama_urls: []\n", encoding="utf-8"
        )
        reset_settings_cache()
        result = runner.invoke(app, ["review", "path", str(test_file), "--no-static-scan"])
        assert result.exit_code != 0
        assert "ai.ollama_urls" in result.output or "ollama_urls" in result.output
    finally:
        test_file.unlink(missing_ok=True)


def test_gateway_only_config_routes_all_calls_to_gateway(
    isolate_devops_cli_config: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With gateway-only config, fake transport verifies calls go to gateway URL and never localhost:11434."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.rag.embeddings import EmbeddingsEngine
    from devops_cli.config.settings import load_settings

    existing_cfg = isolate_devops_cli_config.read_text(encoding="utf-8")
    isolate_devops_cli_config.write_text(
        existing_cfg + "\nai:\n"
        "  provider: gateway\n"
        "  gateway_url: https://192.0.2.1:4000/v1\n"
        "  ollama_urls: []\n"
        "  allow_private_network: true\n"
        "  cache:\n"
        "    enabled: false\n",
        encoding="utf-8",
    )
    reset_settings_cache()
    settings = load_settings()

    requested_urls: list[str] = []

    def mock_send(_self: Any, request: httpx2.Request, **_kwargs: Any) -> httpx2.Response:
        url_str = str(request.url)
        requested_urls.append(url_str)
        if "embeddings" in url_str:
            body = {"data": [{"index": 0, "embedding": [0.1, 0.2]}], "usage": {"total_tokens": 5}}
        else:
            body = {
                "choices": [{"message": {"role": "assistant", "content": "mocked response"}}],
                "usage": {"total_tokens": 10},
            }
        return as_requested(request, httpx2.Response(200, json=body, request=request))

    monkeypatch.setattr(httpx2.Client, "send", mock_send)

    # 1. LLMClient call
    client = LLMClient(config=settings.ai, api_key="sk-test", cache_enabled=False)
    resp = client.chat(system="system", user="user")
    assert resp.text == "mocked response"

    # 2. Embedding call
    embedder = EmbeddingsEngine(ai_config=settings.ai, api_key="sk-test", valkey_client=None)
    embedder.embed_query("query")

    # Assert all calls went to the gateway and NONE to localhost:11434
    ai_requests = [u for u in requested_urls if not u.endswith("/traces")]
    assert len(ai_requests) >= 2
    for url in ai_requests:
        assert url.startswith("https://192.0.2.1:4000/v1")
    assert not any("11434" in u for u in requested_urls)
    assert not any("localhost" in u for u in ai_requests)
