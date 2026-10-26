"""Tests for review dry-run model request preview and child process isolation (#1430)."""

from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from devops_cli.ai.client import get_llm_client
from devops_cli.config.settings import AIConfig
from devops_cli.core.process import DEFAULT_ALLOWED_ENV_VARS, run_subprocess
from devops_cli.dry_run.state import set_dry_run
from devops_cli.exceptions import ConfigurationError
from tests.llm_stream_fakes import route_client


def _llm_request_preview(*args: Any, **kwargs: Any) -> Any:
    from devops_cli.ai.review import runner

    fn = getattr(runner, "_llm_request_preview", None)
    if fn is None:
        raise AttributeError("devops_cli.ai.review.runner has no '_llm_request_preview'")
    return fn(*args, **kwargs)


def _make_canned_reply(request: httpx2.Request) -> httpx2.Response:
    """Return a minimal valid response matching the requested provider endpoint."""
    path = request.url.path
    if request.method == "GET":
        return httpx2.Response(200, json={"id": "test-model", "type": "model", "capabilities": {}})
    if "/messages" in path:
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "review ok"}],
                "model": "claude-3-7-sonnet",
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )
    if "/api/chat" in path or path.endswith("/chat"):
        return httpx2.Response(
            200,
            json={"message": {"role": "assistant", "content": "review ok"}, "done": True},
        )
    return httpx2.Response(
        200,
        json={
            "id": "chatcmpl_test",
            "object": "chat.completion",
            "created": 12345,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "review ok"},
                    "finish_reason": "stop",
                }
            ],
        },
    )


@pytest.mark.parametrize(
    ("provider", "config_kwargs"),
    [
        (
            "ollama",
            {
                "model": "llama3.2:3b",
                "ollama_urls": ["https://example.com:11434"],
            },
        ),
        (
            "claude",
            {
                "model": "claude-3-7-sonnet",
                "api_base_url": "https://example.com/anthropic",
                "api_key": "secret-claude-key",
            },
        ),
        (
            "openai",
            {
                "model": "gpt-4o",
                "api_base_url": "https://example.com/v1",
                "api_key": "secret-openai-key",
            },
        ),
        (
            "copilot",
            {
                "model": "copilot-model",
                "api_base_url": "https://example.com/copilot",
                "api_key": "secret-copilot-key",
            },
        ),
        (
            "gateway",
            {
                "model": "gateway-model",
                "gateway_url": "https://example.com/gw",
                "api_key": "secret-gateway-key",
            },
        ),
    ],
)
def test_review_dry_run_preview_matches_real_call(
    monkeypatch: pytest.MonkeyPatch, provider: str, config_kwargs: dict[str, Any]
) -> None:
    """The dry-run preview equals the request a real call records through the HTTP edge fake."""
    cfg = AIConfig(provider=provider, allow_private_network=True, **config_kwargs)
    client = get_llm_client(config=cfg)

    system_prompt = "You are a code reviewer."
    user_prompt = "Please review this snippet."

    # 1. Record real call through HTTP edge fake
    real_requests = route_client(client, monkeypatch, _make_canned_reply)
    client.chat(system_prompt, user_prompt)
    assert len(real_requests) >= 1
    real_post = [r for r in real_requests if r.method == "POST"][-1]

    # 2. Get dry-run preview
    preview = _llm_request_preview(client, system_prompt, user_prompt)

    # 3. Assert method, URL, and body match
    assert preview["method"] == real_post.method
    assert preview["endpoint"] == str(real_post.url)
    assert preview["url"] == str(real_post.url)

    real_body = json.loads(real_post.content.decode("utf-8"))
    assert preview["json"] == real_body
    assert preview["body"] == real_body

    # 4. Assert preview equality with request
    assert preview == real_post

    # 5. Assert credentials in headers are masked
    preview_headers = {k.lower(): v for k, v in preview["headers"].items()}
    if "authorization" in preview_headers:
        assert "secret-" not in preview_headers["authorization"]
    if "x-api-key" in preview_headers:
        assert "secret-" not in preview_headers["x-api-key"]


def test_review_dry_run_ollama_missing_url_reports_configuration_error() -> None:
    """With no Ollama URL configured, dry-run preview reports missing setting, never localhost."""
    cfg = AIConfig(
        provider="ollama", model="llama3.2:3b", ollama_urls=[], allow_private_network=True
    )
    client = get_llm_client(config=cfg)

    with pytest.raises(ConfigurationError) as exc_info:
        _llm_request_preview(client, "system", "user")

    assert "ai.ollama_urls" in str(exc_info.value) or "No Ollama server URLs configured" in str(
        exc_info.value
    )


def test_review_dry_run_starts_no_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run execution starts no gh process."""
    spawned_cmds: list[list[str]] = []

    from devops_cli.core import process as proc_module

    real_run = proc_module.DefaultProcessRunner.run

    def record_run(self: Any, cmd: Any, *args: Any, **kwargs: Any) -> Any:
        full_cmd = list(cmd)
        spawned_cmds.append(full_cmd)
        if full_cmd and full_cmd[0] == "gh":
            pytest.fail(f"Dry run should start no gh, but spawned: {full_cmd}")
        return real_run(self, cmd, *args, **kwargs)

    monkeypatch.setattr(proc_module.DefaultProcessRunner, "run", record_run)
    proc_module.reset_github_token()
    set_dry_run(True)
    try:
        proc = run_subprocess(["git", "status"], check=False)
        assert proc.returncode == 0
        assert not any(cmd and cmd[0] == "gh" for cmd in spawned_cmds)
    finally:
        set_dry_run(False)
        proc_module.reset_github_token()


def test_default_allowed_env_vars_preserves_session_bus_isolation() -> None:
    """Sanitized subprocess environment preserves XDG_RUNTIME_DIR and DBUS_SESSION_BUS_ADDRESS."""
    assert "XDG_RUNTIME_DIR" in DEFAULT_ALLOWED_ENV_VARS
    assert "DBUS_SESSION_BUS_ADDRESS" in DEFAULT_ALLOWED_ENV_VARS
