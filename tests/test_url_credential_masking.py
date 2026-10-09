"""Tests for URL credential masking, fail-closed handling, telemetry sanitization, and served_by extraction."""

from __future__ import annotations

import subprocess
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.ai.client.network import extract_served_by
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.security.sanitizer import (
    mask_uri_credentials,
    redact_text,
    sanitize_telemetry_endpoint,
)
from devops_cli.security.vault_broker import VaultSecretBroker


def _eval_ssrf_target(input_str: str) -> Any:
    return SSRFBlockedError(input_str).details["target_url"]


def _eval_ssrf_msg_and_target(input_str: str) -> Any:
    err = SSRFBlockedError(input_str)
    return (str(err), err.details["target_url"])


def _eval_ssrf_fail_closed(input_str: str) -> Any:
    err = SSRFBlockedError(input_str)
    assert "169.254" not in str(err)
    return (err.details["target_url"], str(err))


_DISPATCH: dict[str, Any] = {
    "ssrf_target": _eval_ssrf_target,
    "ssrf_msg_and_target": _eval_ssrf_msg_and_target,
    "ssrf_fail_closed": _eval_ssrf_fail_closed,
    "mask_uri": mask_uri_credentials,
    "redact_text": redact_text,
    "telemetry": sanitize_telemetry_endpoint,
}


@pytest.mark.parametrize(
    ("input_str", "func_name", "expected"),
    [
        (
            "https://user:password@ss@example.com/x",
            "ssrf_target",
            "https://user:***@example.com/x",
        ),
        (
            "http://u:" + 300 * "p" + "@example.com/",
            "ssrf_target",
            "http://u:***@example.com/",
        ),
        (
            "http://192.0.2.1:8000/api",
            "ssrf_msg_and_target",
            (
                "SSRF blocked: http://<masked>:8000/api (Target resolves to a private or loopback network endpoint)",
                "http://192.0.2.1:8000/api",
            ),
        ),
        (
            "http://169.254.169.254:abc/",
            "ssrf_fail_closed",
            (
                "<masked-url>",
                "SSRF blocked: <masked-url> (Target resolves to a private or loopback network endpoint)",
            ),
        ),
        (
            "https://user:password@[2001:db8::1]:8080/p",
            "mask_uri",
            "https://user:***@[2001:db8::1]:8080/p",
        ),
        (
            "mysql://root:pa/ss@example.com/x",
            "mask_uri",
            "<masked-url>",
        ),
        (
            "http://u:pa#ss@example.com/",
            "mask_uri",
            "<masked-url>",
        ),
        (
            "mysql://root:12/34@example.com/x",
            "mask_uri",
            "<masked-url>",
        ),
        (
            "http://u:1234#abc@example.com/",
            "mask_uri",
            "<masked-url>",
        ),
        (
            "http://:secret@example.com:8080/data",
            "mask_uri",
            "http://***@example.com:8080/data",
        ),
        (
            "https://user:password@ss@example.com/x",
            "redact_text",
            "https://<masked-user>:<masked-password>@example.com/x",
        ),
        (
            "http://user:password@example.com/x",
            "redact_text",
            "http://<masked-user>:<masked-password>@example.com/x",
        ),
        (
            "postgres://app:s3cret@example.com/x",
            "redact_text",
            "postgres://<masked-user>:<masked-password>@example.com/x",
        ),
        (
            "redis://:pw@example.com:6379",
            "redact_text",
            "redis://<masked-user>:<masked-password>@example.com:6379",
        ),
        (
            "HTTP://U:PW@example.com/",
            "redact_text",
            "HTTP://<masked-user>:<masked-password>@example.com/",
        ),
        (
            "http://:secret@example.com/",
            "redact_text",
            "http://<masked-user>:<masked-password>@example.com/",
        ),
        (
            '["http://example.com","https://user:password@example.com/x"]',
            "redact_text",
            '["http://example.com","https://<masked-user>:<masked-password>@example.com/x"]',
        ),
        (
            '["http://example.com","https://user:password@example.com"]',
            "redact_text",
            '["http://example.com","<masked-url>',
        ),
        (
            "https://example.com/login?next=https://user:password@example.com/x",
            "redact_text",
            "https://example.com/login?next=https://<masked-user>:<masked-password>@example.com/x",
        ),
        (
            "url=http://example.com;db=postgres://u:pw@example.com/x",
            "redact_text",
            "url=http://example.com;db=postgres://<masked-user>:<masked-password>@example.com/x",
        ),
        (
            "mysql://root:pa/ss@example.com/x",
            "redact_text",
            "<masked-url>",
        ),
        (
            "http://u:pa#ss@example.com/",
            "redact_text",
            "<masked-url>",
        ),
        (
            "mysql://root:12/34@example.com/x",
            "redact_text",
            "mysql://root:12/34@example.com/x",
        ),
        (
            "http://u:1234#abc@example.com/",
            "redact_text",
            "http://u:1234#abc@example.com/",
        ),
        (
            'f"postgresql://{user}:{password}@{host}:{port}/{db}"',
            "redact_text",
            'f"postgresql://<masked-user>:<masked-password>@{host}:{port}/{db}"',
        ),
        (
            '<a href="https://user:password@example.com/x">x</a>',
            "redact_text",
            '<a href="https://<masked-user>:<masked-password>@example.com/x">x</a>',
        ),
        (
            "http://example.com:8080/p?email=a@example.com",
            "redact_text",
            "http://example.com:8080/p?email=a@example.com",
        ),
        (
            'x = "http://[" + h',
            "redact_text",
            'x = "http://[" + h',
        ),
        (
            "custom://myuser@example.com/path",
            "mask_uri",
            "custom://myuser@example.com/path",
        ),
        (
            "custom://myuser@example.com/path",
            "redact_text",
            "custom://myuser@example.com/path",
        ),
        (
            "https://ghp_x@example.com/o/r",
            "mask_uri",
            "https://ghp_x@example.com/o/r",
        ),
        (
            "https://ghp_x@example.com/o/r",
            "redact_text",
            "https://ghp_x@example.com/o/r",
        ),
        (
            "http://[::1]:4318",
            "telemetry",
            "http://[::1]:4318",
        ),
        (
            "http://100.64.1.2:4318",
            "telemetry",
            "http://internal-ip:4318",
        ),
        (
            "http://user:pw@203.0.113.5:4318/v1/traces",
            "telemetry",
            "http://internal-ip:4318/v1/traces",
        ),
        (
            "http://[invalid-ipv6",
            "telemetry",
            "<internal-endpoint>",
        ),
    ],
)
def test_acceptance_criteria_table(input_str: str, func_name: str, expected: Any) -> None:
    """Parametrized acceptance criteria table testing URL credential masking behaviors."""
    evaluator = _DISPATCH[func_name]
    assert evaluator(input_str) == expected


def test_vault_broker_status_span_masks_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify VAULT_ADDR credentials are masked on the get_status span attribute."""
    captured_attrs: dict[str, Any] = {}

    def fake_trace_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
        if attributes:
            captured_attrs.update(attributes)
        return nullcontext()

    monkeypatch.setattr("devops_cli.security.vault_broker.trace_span", fake_trace_span)
    monkeypatch.setattr(
        "devops_cli.security.vault_broker.vault_request",
        lambda *args, **kwargs: MagicMock(json=lambda: {"initialized": True, "sealed": False}),
    )

    broker = VaultSecretBroker(vault_addr="https://admin:supersecret@example.com:8200")
    status = broker.get_status()

    assert (
        status.is_healthy,
        "supersecret" not in captured_attrs.get("vault_addr", ""),
        captured_attrs.get("vault_addr"),
    ) == (True, True, "https://admin:***@example.com:8200")


def test_extract_served_by_strips_userinfo() -> None:
    """Verify extract_served_by extracts and sanitizes the gateway served_by header."""
    assert (
        extract_served_by({"x-litellm-model-api-base": "https://user:pw@example.com:11434"}),
        extract_served_by({"x-litellm-model-api-base": "http://u:12/34@example.com:11434"}),
        extract_served_by({"x-litellm-model-api-base": "localhost:11434"}),
        extract_served_by(None),
        extract_served_by({}),
    ) == (
        "https://example.com:11434",
        None,
        "localhost:11434",
        None,
        None,
    )


def test_gateway_served_by_blocking_and_streaming_strips_credentials(
    monkeypatch: pytest.MonkeyPatch,
    public_dns: str,
) -> None:
    """Verify served_by header strips credentials on blocking and streaming OpenAI-compat clients."""
    from devops_cli.ai.client import LLMClient
    from devops_cli.ai.client.network import stream_served_by
    from devops_cli.config.settings import AIConfig
    from devops_cli.models.ai import ChatMessage
    from tests.llm_stream_fakes import route_llm_clients

    client = LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url="http://gateway.example.com:4000/v1",
            model="devops-review",
        ),
        api_key="sk-gateway",
        cache_enabled=False,
    )

    body = {"choices": [{"message": {"content": "OK"}}], "usage": {"completion_tokens": 1}}
    route_llm_clients(
        monkeypatch,
        lambda request: httpx2.Response(
            200,
            json=body,
            headers={"x-litellm-model-api-base": "https://user:pw@example.com:11434"},
        ),
    )

    reply = client.chat("system", "hello", use_cache=False)
    assert (reply.served_by, "pw" not in str(reply.served_by)) == (
        "https://example.com:11434",
        True,
    )

    # Suspicious userinfo fails closed to None
    route_llm_clients(
        monkeypatch,
        lambda request: httpx2.Response(
            200,
            json=body,
            headers={"x-litellm-model-api-base": "http://u:12/34@example.com:11434"},
        ),
    )
    reply2 = client.chat("system", "hello", use_cache=False)
    assert reply2.served_by is None

    # Streaming path
    sse = b'data: {"choices": [{"delta": {"content": "OK"}}]}\n\ndata: [DONE]\n\n'

    def fake_send(self: Any, request: httpx2.Request, **kwargs: Any) -> httpx2.Response:
        headers = {
            "x-litellm-model-api-base": "https://user:pw@example.com:11434",
            "content-type": "text/event-stream",
        }
        return httpx2.Response(200, headers=headers, content=sse, request=request)

    monkeypatch.setattr(httpx2.Client, "send", fake_send)

    stream_served_by.set(None)
    text = "".join(
        client.chat_messages_stream("system", [ChatMessage(role="user", content="hello")])
    )
    assert (text, stream_served_by.get()) == ("OK", "https://example.com:11434")

    # Streaming path with invalid userinfo
    def fake_send_invalid(self: Any, request: httpx2.Request, **kwargs: Any) -> httpx2.Response:
        headers = {
            "x-litellm-model-api-base": "http://u:12/34@example.com:11434",
            "content-type": "text/event-stream",
        }
        return httpx2.Response(200, headers=headers, content=sse, request=request)

    monkeypatch.setattr(httpx2.Client, "send", fake_send_invalid)
    stream_served_by.set(None)
    "".join(client.chat_messages_stream("system", [ChatMessage(role="user", content="hello")]))
    assert stream_served_by.get() is None


def test_free_text_masking_speed() -> None:
    """Verify candidate URL masking takes under 1.0 second across 100 KB fixtures."""
    cases = [
        (
            "100 KB with 1000 credential URLs",
            ("https://user:secret123@example.com/path " * 1000)[:100_000],
            "secret123",
        ),
        ("100 KB letters with no ://", "a" * 100_000, None),
        ("100 KB no whitespace with 25000 a://", ("a://" * 25_000)[:100_000], None),
        ("100 KB repeated credential URL", ("https://user:pw@example.com," * 4000)[:100_000], "pw"),
    ]
    for label, text, secret in cases:
        start = time.perf_counter()
        redacted = redact_text(text)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"{label} exceeded 1s: {elapsed:.3f}s"
        if secret:
            assert secret not in redacted, f"{label} leaked {secret}"


def test_no_forbidden_constructs_remain() -> None:
    """Verify architectural invariants: forbidden regex patterns and legacy shims are gone."""
    repo_root = Path(__file__).resolve().parent.parent

    # 1. Check forbidden regexes and constructs
    cmd1 = [
        "git",
        "grep",
        "-n",
        "-F",
        "-e",
        "_replace(netloc",
        "-e",
        'partition("@")',
        "-e",
        "https?://[^",
        "-e",
        "://([^:]*)",
        "src/devops_cli/exceptions/security.py",
        "src/devops_cli/security/sanitizer.py",
    ]
    res1 = subprocess.run(cmd1, cwd=repo_root, capture_output=True, text=True)
    assert (res1.returncode, res1.stdout.strip()) == (1, "")

    # 2. Check mask_uri_credentials(str(
    cmd2 = ["git", "grep", "-n", "mask_uri_credentials(str(", "src"]
    res2 = subprocess.run(cmd2, cwd=repo_root, capture_output=True, text=True)
    assert (res2.returncode, res2.stdout.strip()) == (1, "")

    # 3. Check legacy endpoint helper is removed
    target_ident = "_sanitize_" + "telemetry_endpoint"
    cmd3 = [
        "git",
        "grep",
        "-E",
        rf"\b{target_ident}\b",
        "src",
        "tests",
        ":^tests/test_url_credential_masking.py",
    ]
    res3 = subprocess.run(cmd3, cwd=repo_root, capture_output=True, text=True)
    assert (res3.returncode, res3.stdout.strip()) == (1, "")

    # 4. Check served_by header references: only constants.py and network.py
    cmd4 = [
        "git",
        "grep",
        "-n",
        "-E",
        "CONST_AI_GATEWAY_SERVED_BY_HEADER|x-litellm-model-api-base",
        "src",
    ]
    res4 = subprocess.run(cmd4, cwd=repo_root, capture_output=True, text=True)
    lines = [line.split(":")[0] for line in res4.stdout.strip().splitlines() if line]
    assert (
        res4.returncode == 0
        and len(lines) >= 2
        and all(
            p.endswith("config/constants.py") or p.endswith("ai/client/network.py") for p in lines
        )
    )
