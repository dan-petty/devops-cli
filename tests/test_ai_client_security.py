"""Security-focused tests for AI client endpoint handling."""

from __future__ import annotations

import json

import httpx2
import pytest

from devops_cli.ai.client import AIClientError, LLMClient
from devops_cli.config.settings import AIConfig
from devops_cli.models.ai import ChatMessage
from tests.llm_stream_fakes import route_client


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


def test_a_cloud_metadata_api_base_is_refused_even_when_private_hosts_are_allowed() -> None:
    """Verify allow_private_network never opens the cloud metadata service to the client."""
    client = LLMClient(
        AIConfig(
            provider="openai", api_base_url="http://169.254.169.254/v1", allow_private_network=True
        )
    )

    with pytest.raises(AIClientError, match="cloud metadata"):
        client._api_base()


def test_private_api_base_can_be_enabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    client = LLMClient(AIConfig(provider="openai", api_base_url="http://10.0.0.10:9000"))

    assert client._api_base() == "http://10.0.0.10:9000"


def test_configured_loopback_endpoints_need_no_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify every provider's configured loopback endpoint passes, as one policy decides."""
    monkeypatch.delenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", raising=False)
    ollama = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))
    openai = LLMClient(AIConfig(provider="openai", api_base_url="http://127.0.0.1:8000/v1"))
    gateway = LLMClient(AIConfig(provider="gateway", gateway_url="http://localhost:4000/v1"))

    assert (
        ollama._validate_base_url(ollama._config.get_ollama_urls[0], purpose="Ollama"),
        openai._api_base(),
        gateway._api_base(),
    ) == ("http://localhost:11434", "http://127.0.0.1:8000/v1", "http://localhost:4000/v1")


# ── Ollama thinking auto-detect ───────────────────────────────────────────────


def test_ollama_retries_without_thinking_on_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 400 'does not support thinking' triggers a transparent retry without think=True."""
    import httpx2

    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))

    def answer(request: httpx2.Request) -> httpx2.Response:
        if len(sent) == 1:
            return httpx2.Response(
                400, json={"error": "model 'qwen2.5-coder:7b' does not support thinking"}
            )
        return httpx2.Response(200, json={"message": {"role": "assistant", "content": "OK"}})

    sent = route_client(client, monkeypatch, answer)

    reply = client._ollama_messages("sys", [ChatMessage(role="user", content="user")])
    assert reply == "OK"
    assert [json.loads(request.content)["think"] for request in sent] == [True, False]
    assert client._ollama_thinking_supported is False


def test_ollama_subsequent_calls_skip_thinking_after_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After detecting no thinking support, subsequent calls never send think=True."""
    import httpx2

    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))
    client._ollama_thinking_supported = False  # already detected

    sent = route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(
            200, json={"message": {"role": "assistant", "content": "OK"}}
        ),
    )

    client._ollama_messages("sys", [ChatMessage(role="user", content="user")])

    assert [json.loads(request.content)["think"] for request in sent] == [False]


def test_ollama_non_thinking_400_raises_ai_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 400 unrelated to thinking is surfaced as AIClientError, not retried."""
    import httpx2

    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))

    route_client(
        client, monkeypatch, lambda request: httpx2.Response(400, json={"error": "model not found"})
    )

    with pytest.raises(AIClientError, match="HTTP 400"):
        client._ollama_messages("sys", [ChatMessage(role="user", content="user")])


def test_get_ollama_urls_parsing() -> None:
    cfg1 = AIConfig(ollama_urls=["http://172.16.0.1:11434", "http://172.16.0.2:11434/"])
    assert cfg1.get_ollama_urls == ["http://172.16.0.1:11434", "http://172.16.0.2:11434"]

    cfg2 = AIConfig(ollama_urls=["http://10.0.0.1:11434/", "http://10.0.0.2:11434"])
    assert cfg2.get_ollama_urls == ["http://10.0.0.1:11434", "http://10.0.0.2:11434"]


def test_ollama_multiserver_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx2

    cfg = AIConfig(
        provider="ollama",
        ollama_urls=["http://localhost:11434", "http://localhost:11435"],
    )
    client = LLMClient(cfg)

    def answer(request: httpx2.Request) -> httpx2.Response:
        if request.url.port == 11434:
            raise httpx2.ConnectError("Connection refused", request=request)
        return httpx2.Response(
            200, json={"message": {"role": "assistant", "content": "Hello from server 2"}}
        )

    sent = route_client(client, monkeypatch, answer)
    monkeypatch.setattr(LLMClient, "_load_and_increment_rr_index", classmethod(lambda cls, n: 0))

    reply = client._ollama_messages("sys", [ChatMessage(role="user", content="hi")])
    assert reply == "Hello from server 2"
    assert [str(request.url) for request in sent] == [
        "http://localhost:11434/api/chat",
        "http://localhost:11435/api/chat",
    ]


# Copies of `devops_cli.ai.client.network`'s round-robin and slot state that the client once
# kept. A copy of the index was taken once, at class creation, and never followed the module's.
_LEGACY_OLLAMA_RR_STATE = (
    "_global_ollama_url_index",
    "_global_ollama_url_lock",
    "_ollama_active_lock",
    "_ollama_semaphores",
    "_ollama_sem_lock",
    "_active_ollama_requests",
)


def test_llmclient_has_no_legacy_ollama_rr_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the client keeps no copy of the module's round-robin state and orders by it."""
    client = LLMClient(
        AIConfig(
            provider="ollama", ollama_urls=["http://example.com:11434", "http://example.com:11435"]
        )
    )
    monkeypatch.setattr(LLMClient, "_load_and_increment_rr_index", classmethod(lambda cls, n: 1))

    order = [url for _index, url in client._get_ollama_urls_loop()]

    assert (
        [name for name in _LEGACY_OLLAMA_RR_STATE if hasattr(LLMClient, name)],
        [name for name in ("_ollama_url_index", "_ollama_url_lock") if name in vars(client)],
        order,
    ) == ([], [], ["http://example.com:11435", "http://example.com:11434"])


def test_preload_models(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AIConfig(
        provider="ollama",
        model="gemma4:26b",
        ollama_urls=["http://localhost:11434", "http://localhost:11435"],
    )
    client = LLMClient(cfg)
    requested: list[str] = []

    def fake_post(_self: object, url: str, **kwargs: object) -> httpx2.Response:
        requested.append(url)
        return httpx2.Response(200, json={"status": "success"}, request=httpx2.Request("POST", url))

    monkeypatch.setattr("httpx2.Client.post", fake_post)
    results = client.preload_models()
    assert results == {"http://localhost:11434": True, "http://localhost:11435": True}
    assert len(requested) == 2
    assert "http://localhost:11434/api/generate" in requested
    assert "http://localhost:11435/api/generate" in requested


def test_preload_models_non_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    cfg = AIConfig(
        provider="ollama",
        model="gemma4:26b",
        ollama_urls=["http://localhost:11434"],
    )
    client = LLMClient(cfg)
    completed_event = threading.Event()
    callback_results: dict[str, bool] = {}

    def fake_post(_self: object, url: str, **kwargs: object) -> httpx2.Response:
        return httpx2.Response(200, json={"status": "success"}, request=httpx2.Request("POST", url))

    def on_done(res: dict[str, bool]) -> None:
        callback_results.update(res)
        completed_event.set()

    monkeypatch.setattr("httpx2.Client.post", fake_post)
    client.prewarm_async(on_complete=on_done)
    assert completed_event.wait(timeout=2.0)
    assert callback_results == {"http://localhost:11434": True}


def test_llm_response_processing_time(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"])
    client = LLMClient(cfg)

    route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Done"},
                "prompt_eval_duration": 4_000_000_000,
                "eval_duration": 6_000_000_000,
                "total_duration": 60_000_000_000,
            },
        ),
    )
    res = client.chat("sys", "user")
    assert isinstance(res, str)
    assert res == "Done"
    assert res.processing_seconds == 10.0


def test_ollama_max_parallel_concurrency_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    cfg = AIConfig(
        provider="ollama",
        ollama_urls=["http://localhost:11434"],
        ollama_max_parallel=2,
    )
    client = LLMClient(cfg)
    concurrent_active = 0
    max_observed_concurrent = 0
    lock = threading.Lock()

    def answer(request: httpx2.Request) -> httpx2.Response:
        nonlocal concurrent_active, max_observed_concurrent
        with lock:
            concurrent_active += 1
            max_observed_concurrent = max(max_observed_concurrent, concurrent_active)
        time.sleep(0.05)
        with lock:
            concurrent_active -= 1
        return httpx2.Response(
            200, json={"message": {"role": "assistant", "content": "Parallel reply"}}
        )

    route_client(client, monkeypatch, answer)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(client.chat, "sys", f"user {i}") for i in range(5)]
        results = [f.result() for f in futures]

    assert len(results) == 5
    assert all(r == "Parallel reply" for r in results)
    assert max_observed_concurrent <= 2


def test_ollama_error_message_masks_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))

    route_client(
        client,
        monkeypatch,
        lambda request: httpx2.Response(
            500,
            text="Internal error with token=ghp_secret123456789012345678901234567890 and key=sk-ant-secret12345678901234567890",
        ),
    )

    with pytest.raises(AIClientError) as exc_info:
        client._try_single_ollama_request(
            "http://localhost:11434", "http://localhost:11434", "sys", [], False, 1
        )

    err_msg = str(exc_info.value)
    assert "ghp_secret" not in err_msg
    assert "sk-ant-secret" not in err_msg
    assert "<masked-github-token>" in err_msg


def test_ollama_stream_error_message_masks_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LLMClient(AIConfig(provider="ollama", ollama_urls=["http://localhost:11434"]))

    def fake_stream(_self: object, method: str, url: str, **kwargs: object) -> object:
        req = httpx2.Request(method, url)
        resp = httpx2.Response(
            502,
            text="Gateway error containing token=ghp_secret987654321098765432109876543210",
            request=req,
        )
        raise httpx2.HTTPStatusError("502 Bad Gateway", request=req, response=resp)

    monkeypatch.setattr("httpx2.Client.stream", fake_stream)

    with pytest.raises(AIClientError) as exc_info:
        list(
            client._try_single_ollama_stream(
                "http://localhost:11434", "http://localhost:11434", "sys", [], False, 1
            )
        )

    err_msg = str(exc_info.value)
    assert "ghp_secret" not in err_msg
    assert "<masked-github-token>" in err_msg
