"""Security-focused tests for AI client endpoint handling."""

from __future__ import annotations

import pytest

from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage


def test_connection_error_hides_ollama_url() -> None:
    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://10.1.2.3:11434"]))

    err = client._connection_error(RuntimeError("boom"))

    assert "10.1.2.3" not in str(err)
    assert "Cannot connect to Ollama" in str(err)


def test_private_api_base_is_rejected_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    client = LLMClient(AIConfig(provider="openai", api_base_url="http://10.0.0.10:9000"))

    with pytest.raises(AIClientError, match="Refusing non-public provider API URL"):
        client._api_base()


def test_private_api_base_can_be_enabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    client = LLMClient(AIConfig(provider="openai", api_base_url="http://10.0.0.10:9000"))

    assert client._api_base() == "http://10.0.0.10:9000"


def test_ollama_allows_localhost_without_env_override() -> None:
    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))

    validated = client._validate_base_url(
        client._config.get_ollama_urls[0],
        purpose="Ollama",
        allow_loopback_for_local_tooling=True,
    )

    assert validated == "http://localhost:11434"


# ── Ollama thinking auto-detect ───────────────────────────────────────────────


def test_ollama_retries_without_thinking_on_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 400 'does not support thinking' triggers a transparent retry without think=True."""
    import httpx2

    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))

    call_count = 0

    def fake_post(_client: object, url: str, **kwargs: object) -> httpx2.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx2.Response(
                400,
                json={"error": "model 'qwen2.5-coder:7b' does not support thinking"},
                request=httpx2.Request("POST", url),
            )
        return httpx2.Response(
            200,
            json={"message": {"role": "assistant", "content": "OK"}},
            request=httpx2.Request("POST", url),
        )

    monkeypatch.setattr("httpx2.Client.post", fake_post)

    reply = client._ollama_messages("sys", [ChatMessage(role="user", content="user")])
    assert reply == "OK"
    assert call_count == 2
    assert client._ollama_thinking_supported is False


def test_ollama_subsequent_calls_skip_thinking_after_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After detecting no thinking support, subsequent calls never send think=True."""
    import httpx2

    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))
    client._ollama_thinking_supported = False  # already detected

    think_values: list[bool] = []

    def fake_post(_client: object, url: str, **kwargs: object) -> httpx2.Response:
        payload = kwargs.get("json", {})
        think_values.append(bool(payload.get("think")))  # type: ignore[union-attr]
        return httpx2.Response(
            200,
            json={"message": {"role": "assistant", "content": "OK"}},
            request=httpx2.Request("POST", url),
        )

    monkeypatch.setattr("httpx2.Client.post", fake_post)

    client._ollama_messages("sys", [ChatMessage(role="user", content="user")])

    assert think_values == [False]


def test_ollama_non_thinking_400_raises_ai_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 400 unrelated to thinking is surfaced as AIClientError, not retried."""
    import httpx2

    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))

    def fake_post(_client: object, url: str, **kwargs: object) -> httpx2.Response:
        return httpx2.Response(
            400,
            json={"error": "model not found"},
            request=httpx2.Request("POST", url),
        )

    monkeypatch.setattr("httpx2.Client.post", fake_post)

    with pytest.raises(AIClientError, match="HTTP 400"):
        client._ollama_messages("sys", [ChatMessage(role="user", content="user")])


def test_get_ollama_urls_parsing() -> None:
    cfg1 = AIConfig(ollama_urls=["http://192.168.1.4:11434", "http://192.168.1.5:11434/"])
    assert cfg1.get_ollama_urls == ["http://192.168.1.4:11434", "http://192.168.1.5:11434"]

    cfg2 = AIConfig(ollama_urls=["http://10.0.0.1:11434/", "http://10.0.0.2:11434"])
    assert cfg2.get_ollama_urls == ["http://10.0.0.1:11434", "http://10.0.0.2:11434"]


def test_ollama_multiserver_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx2

    cfg = AIConfig(
        provider="ollama",
        ollama_urls=["http://localhost:11434", "http://localhost:11435"],
    )
    client = LLMClient(cfg)

    requested_urls: list[str] = []

    def fake_post(_client: object, url: str, **kwargs: object) -> httpx2.Response:
        requested_urls.append(url)
        if "11434" in url:
            raise httpx2.ConnectError("Connection refused", request=httpx2.Request("POST", url))
        return httpx2.Response(
            200,
            json={"message": {"role": "assistant", "content": "Hello from server 2"}},
            request=httpx2.Request("POST", url),
        )

    monkeypatch.setattr("httpx2.Client.post", fake_post)

    reply = client._ollama_messages("sys", [ChatMessage(role="user", content="hi")])
    assert reply == "Hello from server 2"
    assert requested_urls == [
        "http://localhost:11434/api/chat",
        "http://localhost:11435/api/chat",
    ]
    assert client._ollama_url_index == 1
