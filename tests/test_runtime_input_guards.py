"""Unit tests for agent runtime security: URI traversal, secret masking, and injection guards."""

from __future__ import annotations

import pytest

from devops_cli.ai.diff.difftastic import get_structural_diff
from devops_cli.k8s.chaos_runner import ChaosExperiment, ChaosFaultRunner
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.security.vault_broker import parse_vault_uri

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


# ── 2. Secret Sanitizer Regex Identifier Protection ──────────────────────────


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


# ── 3. ChaosFaultRunner Argument Injection Guards ────────────────────────────


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
    assert report.error is not None
    assert (
        "invalid" in report.error.lower()
        or "flag" in report.error.lower()
        or "injection" in report.error.lower()
        or "failed" in report.error.lower()
    )


# ── 4. Structural Diff Ref Injection Guards ──────────────────────────────────


def test_structural_diff_rejects_flag_injection_refs() -> None:
    """Verify that get_structural_diff rejects branch/base with leading hyphens."""
    res = get_structural_diff(
        path_a="src/devops_cli/main.py",
        branch="--output=/tmp/evil",
        base="main",
    )
    assert "Error:" in res or res == ""
