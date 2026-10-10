"""Unit tests for network security validation, SSRF protection, and OpenTelemetry trace correlation in logs."""

from __future__ import annotations

import logging
import socket

import pytest

from devops_cli.commands.k8s.cluster_context import apply as k8s_apply
from devops_cli.security.sanitizer import sanitize_telemetry_endpoint
from devops_cli.security.vault_broker import VaultSecretBroker, parse_vault_uri
from devops_cli.telemetry.logging_bridge import (
    TraceCorrelationFilter,
    get_current_trace_correlation,
)

# ── Finding #8: SSRF DNS Resolution in Manifest URL ──────────────────────────


def test_k8s_apply_manifest_ssrf_rejects_hostname_resolving_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """k8s apply rejects manifest URLs whose hostname resolves to private/loopback/link-local IP."""

    for fake_ip in ("10.0.1.5", "169.254.169.254", "127.0.0.1"):
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port, *args, fake_ip=fake_ip, **kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (fake_ip, 80))
            ],
        )
        with pytest.raises(
            ValueError,
            match=r"(Manifest URL resolves to private or reserved IP|Access to link-local or cloud metadata services)",
        ):
            k8s_apply("http://example.com/manifest.yaml")


# ── Finding #12: Path Traversal in Vault URI Parsing ─────────────────────────


def test_parse_vault_uri_rejects_path_traversal() -> None:
    """parse_vault_uri rejects URI references containing directory traversal sequences."""
    with pytest.raises(ValueError, match="Path traversal detected in Vault URI"):
        parse_vault_uri("vault://secret/data/devops/../../admin/root_token")

    with pytest.raises(ValueError, match="Path traversal detected in Vault URI"):
        parse_vault_uri("secret/data/ci/../sensitive#token")


def test_vault_broker_get_secret_rejects_traversal_path() -> None:
    """VaultSecretBroker.get_secret rejects traversal paths."""
    broker = VaultSecretBroker(vault_addr="http://127.0.0.1:8200")
    with pytest.raises(ValueError, match="Path traversal detected"):
        broker.get_secret("secret/data/../../root")


# ── Finding #13: Credential Leakage in Telemetry Route ───────────────────────


def test_sanitize_telemetry_endpoint_strips_user_credentials() -> None:
    """sanitize_telemetry_endpoint strips userinfo credentials from OTLP URLs."""
    # Internal IP with credentials
    res_internal = sanitize_telemetry_endpoint("http://admin:supersecret@10.0.0.5:4318/v1/traces")
    assert (
        "supersecret" not in res_internal,
        "admin" not in res_internal,
        "internal-ip" in res_internal,
    ) == (True, True, True)

    # Localhost with credentials
    res_local = sanitize_telemetry_endpoint("http://user:password123@localhost:4318/v1/traces")
    assert (
        "password123" not in res_local,
        "user" not in res_local,
        "localhost:4318" in res_local,
    ) == (True, True, True)

    # Public domain with credentials
    res_public = sanitize_telemetry_endpoint("https://apikey:token456@otlp.cloud.io:4318")
    assert (
        "token456" not in res_public,
        "apikey" not in res_public,
        "otlp.cloud.io:4318" in res_public,
    ) == (True, True, True)


# ── Finding #15: Logging Bridge Defensive Guard for None Context ─────────────


def test_logging_bridge_handles_none_span_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """TraceCorrelationFilter and get_current_trace_correlation handle None span context gracefully."""
    import devops_cli.telemetry.logging_bridge as lb

    monkeypatch.setattr(lb, "get_current_span_context", lambda: None)

    filt = TraceCorrelationFilter()
    rec = logging.LogRecord("test", logging.INFO, "path", 1, "msg", (), None)
    assert filt.filter(rec) is True
    assert getattr(rec, "trace_id") == ""
    assert getattr(rec, "span_id") == ""

    corr = get_current_trace_correlation()
    assert corr == {"trace_id": "", "span_id": ""}


# ── Hallucination Invalidation Tests for Session 20260905-035954 ─────────────
