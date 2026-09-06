"""Unit tests for review session 20260905-035954 remediations and loop hardening."""

from __future__ import annotations

import logging
import socket
from pathlib import Path

import pytest

from devops_cli.ai.review.verification import _deterministic_pre_verification
from devops_cli.ai.review_schema import Finding
from devops_cli.commands.k8s.cluster_context import apply as k8s_apply
from devops_cli.security.vault_broker import VaultSecretBroker, parse_vault_uri
from devops_cli.server.routes.telemetry import _sanitize_telemetry_endpoint
from devops_cli.telemetry.logging_bridge import (
    TraceCorrelationFilter,
    get_current_trace_correlation,
)

# ── Finding #8: SSRF DNS Resolution in Manifest URL ──────────────────────────


def test_k8s_apply_manifest_ssrf_rejects_hostname_resolving_to_private_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """k8s apply rejects manifest URLs whose hostname resolves to private/loopback/link-local IP."""

    def fake_getaddrinfo(host: str, port: object, *args: object, **kwargs: object) -> list[object]:
        if host == "internal.corp.local":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.1.5", 80))]
        if host == "metadata.cloud.internal":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]
        if host == "loopback.domain":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError, match="Manifest URL resolves to private or reserved IP"):
        k8s_apply("http://internal.corp.local/manifest.yaml")

    with pytest.raises(ValueError, match="Manifest URL resolves to private or reserved IP"):
        k8s_apply("http://metadata.cloud.internal/computeMetadata/v1")

    with pytest.raises(ValueError, match="Manifest URL resolves to private or reserved IP"):
        k8s_apply("http://loopback.domain/manifest.yaml")


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
    """_sanitize_telemetry_endpoint strips userinfo credentials from OTLP URLs."""
    # Internal IP with credentials
    res_internal = _sanitize_telemetry_endpoint("http://admin:supersecret@10.0.0.5:4318/v1/traces")
    assert "supersecret" not in res_internal
    assert "admin" not in res_internal
    assert "<internal-ip>" in res_internal

    # Localhost with credentials
    res_local = _sanitize_telemetry_endpoint("http://user:password123@localhost:4318/v1/traces")
    assert "password123" not in res_local
    assert "user" not in res_local
    assert "localhost:4318" in res_local

    # Public domain with credentials
    res_public = _sanitize_telemetry_endpoint("https://apikey:token456@otlp.cloud.io:4318")
    assert "token456" not in res_public
    assert "apikey" not in res_public
    assert "otlp.cloud.io:4318" in res_public


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


def test_deterministic_pre_verification_invalidates_pep758_hallucinations() -> None:
    """Deterministic pre-verification immediately invalidates false PEP 758 syntax claims."""
    finding = Finding(
        severity="CRITICAL",
        location="src/devops_cli/ai/review/verification.py:145-147",
        title="Syntax error in exception handling",
        description="The code uses the deprecated syntax except ValueError, OSError: which is invalid in Python 3.",
        fix="except (ValueError, OSError):",
    )

    verdict = _deterministic_pre_verification(
        finding,
        target_dir=Path.cwd(),
        changed_files=["src/devops_cli/ai/review/verification.py"],
    )
    assert verdict is not None
    assert verdict.status == "INVALIDATED"


def test_deterministic_pre_verification_invalidates_masked_secret_syntax_claim() -> None:
    """Deterministic pre-verification invalidates false syntax claims about masked secrets."""
    finding = Finding(
        severity="CRITICAL",
        location="src/devops_cli/lang/en/errors.py:29",
        title="Invalid identifier '<masked-secret>' causes syntax error",
        description="The field name <masked-secret> in ConfigErrorMessages is not a valid Python identifier.",
        fix="Rename field to valid identifier",
    )

    verdict = _deterministic_pre_verification(
        finding,
        target_dir=Path.cwd(),
        changed_files=["src/devops_cli/lang/en/errors.py"],
    )
    assert verdict is not None
    assert verdict.status == "INVALIDATED"


def test_deterministic_pre_verification_invalidates_monologue_headline() -> None:
    """Deterministic pre-verification invalidates findings with conversational scratchpad titles."""
    finding = Finding(
        severity="MEDIUM",
        location="src/devops_cli/docs/generator.py",
        title='_format_param_default_str: It uses try/except with "except ValueError, AttributeError:" which is Python 2 syntax.',
        description="Chain of thought monologue leaked into finding fields.",
    )

    verdict = _deterministic_pre_verification(
        finding,
        target_dir=Path.cwd(),
        changed_files=["src/devops_cli/docs/generator.py"],
    )
    assert verdict is not None
    assert verdict.status == "INVALIDATED"
