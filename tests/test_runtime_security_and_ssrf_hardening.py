"""Unit tests for agent runtime security: URI traversal, SSRF, secret masking, injection guards."""

from __future__ import annotations

import pytest

from devops_cli.ai.common_tools import web_fetch_tool
from devops_cli.ai.diff.difftastic import get_structural_diff
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.k8s.chaos_runner import ChaosExperiment, ChaosFaultRunner
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.security.vault_broker import parse_vault_uri
from tests.web_fakes import StubWeb

# ── 1. Vault URI Percent-Encoded Traversal Validation ────────────────────────


def test_parse_vault_uri_rejects_percent_encoded_traversal() -> None:
    """Verify that parse_vault_uri catches percent-encoded path traversal sequences."""
    with pytest.raises(ValueError, match="Path traversal detected"):
        parse_vault_uri("vault://secret/%2e%2e/admin/creds")

    with pytest.raises(ValueError, match="Path traversal detected"):
        parse_vault_uri("secret/data/%2E%2E/passwords")

    # Valid URI parses cleanly
    path, key = parse_vault_uri("vault://secret/data/ci/db#password")
    assert path == "secret/data/ci/db"
    assert key == "password"


# ── 2. Web Fetch Tool Case-Insensitive Domains & SSRF ─────────────────────────


def test_web_fetch_tool_case_insensitive_domains(stub_web: StubWeb) -> None:
    """Verify that web_fetch_tool performs case-insensitive domain matching."""
    tool = web_fetch_tool(allowed_domains=["example.com"], blocked_domains=["evil.com"])
    stub_web.page("https://example.com/page", "<html><body><h1>Hello</h1></body></html>")

    # Uppercase domain should match allowed_domains
    res = tool.execute(url="https://EXAMPLE.COM/page")
    assert "# Hello" in res

    # Uppercase blocked domain should be blocked
    with pytest.raises(ValueError, match="blocked_domains"):
        tool.execute(url="https://EVIL.COM/page")


def test_web_fetch_tool_reraises_ssrf_blocked_error() -> None:
    """Verify that SSRFBlockedError is raised directly and not swallowed into a success string."""
    tool = web_fetch_tool()
    with pytest.raises(SSRFBlockedError):
        tool.execute(url="http://127.0.0.1:8080/admin")


# ── 3. Secret Sanitizer Regex Identifier Protection ──────────────────────────


def test_secret_sanitizer_does_not_mask_variable_identifiers() -> None:
    """Verify that _sanitize_diff_secrets does NOT mask Python identifiers like secret_storage_failed."""
    code_diff = (
        "@@ -30,3 +30,3 @@\n"
        '+    secret_storage_failed: str = "Failed to store secret"\n'
        "+    secret_rotation_interval_seconds: int = 3600\n"
    )
    sanitized = mask_secrets(code_diff)
    assert "secret_storage_failed" in sanitized
    assert "<masked-secret>" not in sanitized
    assert "secret_rotation_interval_seconds" in sanitized


def test_secret_sanitizer_masks_actual_secret_assignments() -> None:
    """Verify that actual secret values after assignment or tokens ARE masked."""
    diff = "@@ -10,1 +10,1 @@\n+    api_token = secret_ab12cd34ef56gh78ij90\n"
    sanitized = mask_secrets(diff)
    assert "<masked-secret>" in sanitized or "<masked-token>" in sanitized


# ── 4. ChaosFaultRunner Argument Injection Guards ────────────────────────────


def test_chaos_fault_runner_rejects_argument_injection() -> None:
    """Verify that ChaosFaultRunner rejects namespaces or selectors with argument injection flags."""
    runner = ChaosFaultRunner()
    bad_exp = ChaosExperiment(
        name="test-chaos",
        namespace="--all-namespaces",
        target_label_selector="app=web",
    )
    report = runner.run_experiment(bad_exp)
    assert report.status.value in ("FAILED", "SKIPPED")
    assert report.error is not None and (
        "invalid" in report.error.lower()
        or "flag" in report.error.lower()
        or "injection" in report.error.lower()
        or "failed" in report.error.lower()
    )


# ── 5. Structural Diff Ref Injection Guards ──────────────────────────────────


def test_structural_diff_rejects_flag_injection_refs() -> None:
    """Verify that get_structural_diff rejects branch/base with leading hyphens."""
    res = get_structural_diff(
        path_a="src/devops_cli/main.py",
        branch="--output=/tmp/evil",
        base="main",
    )
    assert "Error:" in res or res == ""
