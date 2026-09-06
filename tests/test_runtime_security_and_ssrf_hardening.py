"""Unit tests for agent runtime security, media storage traversal prevention, and SSRF hardening."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.agents.capabilities import WebFetch
from devops_cli.ai.agents.media import DiskMediaStore
from devops_cli.ai.agents.pydantic_agent import Tool
from devops_cli.ai.common_tools import web_fetch_tool
from devops_cli.ai.diff.difftastic import get_structural_diff
from devops_cli.ai.ext_langchain import _validate_langchain_kwargs
from devops_cli.ai.review.auto_fix import generate_remediation_branch
from devops_cli.ai.review.sanitization import _mask_secrets_in_content
from devops_cli.exceptions.security import SSRFBlockedError
from devops_cli.k8s.chaos_runner import ChaosExperiment, ChaosFaultRunner
from devops_cli.security.vault_broker import parse_vault_uri

# ── 1. DiskMediaStore Traversal & Hash Validation ─────────────────────────────


def test_disk_media_store_rejects_path_traversal() -> None:
    """Verify that DiskMediaStore rejects non-sha256 digests and path traversal in get/delete."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DiskMediaStore(root_dir=tmpdir)

        # Attempt path traversal
        traversal_uri = "media+sha256://../../etc/passwd"
        assert store.get(traversal_uri) is None
        assert store.delete(traversal_uri) is False

        # Attempt non-hex digest
        invalid_uri = "media+sha256://not-a-valid-sha256-hash-too-short"
        assert store.get(invalid_uri) is None
        assert store.delete(invalid_uri) is False

        # Valid sha256 store and retrieve
        valid_digest = "a" * 64
        valid_uri = f"media+sha256://{valid_digest}"
        test_file = Path(tmpdir) / valid_digest
        test_file.write_bytes(b"image content")

        res = store.get(valid_uri)
        assert res is not None
        assert res.data == b"image content"
        assert store.delete(valid_uri) is True
        assert not test_file.exists()


# ── 2. Vault URI Percent-Encoded Traversal Validation ────────────────────────


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


# ── 3. Auto-Fix Path Traversal Validation ────────────────────────────────────


def test_generate_remediation_branch_rejects_traversal() -> None:
    """Verify that generate_remediation_branch rejects target files outside repository boundary."""
    res = generate_remediation_branch(
        finding_id="finding-123",
        target_file="../../etc/passwd",
        dry_run=False,
    )
    assert res.applied is False
    assert (
        "outside" in res.message.lower()
        or "not found" in res.message.lower()
        or "traversal" in res.message.lower()
    )


# ── 4. Web Fetch Tool Case-Insensitive Domains & SSRF ─────────────────────────


def test_web_fetch_tool_case_insensitive_domains() -> None:
    """Verify that web_fetch_tool performs case-insensitive domain matching."""
    tool = web_fetch_tool(allowed_domains=["example.com"], blocked_domains=["evil.com"])

    # Uppercase domain should match allowed_domains
    with patch("devops_cli.ai.common_tools.new_http_client") as mock_client_factory:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.url = MagicMock(host="EXAMPLE.COM", hostname="EXAMPLE.COM")
        mock_resp.content = b"<html><body><h1>Hello</h1></body></html>"
        mock_resp.text = "<html><body><h1>Hello</h1></body></html>"
        mock_resp.status_code = 200
        mock_client.get.return_value = mock_resp
        mock_client_factory.return_value = mock_client

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


# ── 5. WebFetch Capability Propagates Blocked Domains ────────────────────────


def test_web_fetch_capability_propagates_blocked_domains() -> None:
    """Verify that WebFetch capability passes blocked_domains to web_fetch_tool."""
    cap = WebFetch(
        allowed_domains=["example.com"],
        blocked_domains=["blocked.com"],
        local=True,
    )
    tools = cap.get_tools()
    assert len(tools) == 1
    fetch_tool = tools[0]
    assert isinstance(fetch_tool, Tool)

    with pytest.raises(ValueError, match="blocked_domains"):
        fetch_tool.execute(url="https://blocked.com/bad")


# ── 6. Secret Sanitizer Regex Identifier Protection ──────────────────────────


def test_secret_sanitizer_does_not_mask_variable_identifiers() -> None:
    """Verify that _sanitize_diff_secrets does NOT mask Python identifiers like secret_storage_failed."""
    code_diff = (
        "@@ -30,3 +30,3 @@\n"
        '+    secret_storage_failed: str = "Failed to store secret"\n'
        "+    secret_rotation_interval_seconds: int = 3600\n"
    )
    sanitized = _mask_secrets_in_content(code_diff)
    assert "secret_storage_failed" in sanitized
    assert "<masked-secret>" not in sanitized
    assert "secret_rotation_interval_seconds" in sanitized


def test_secret_sanitizer_masks_actual_secret_assignments() -> None:
    """Verify that actual secret values after assignment or tokens ARE masked."""
    diff = "@@ -10,1 +10,1 @@\n+    api_token = secret_ab12cd34ef56gh78ij90\n"
    sanitized = _mask_secrets_in_content(diff)
    assert "<masked-secret>" in sanitized or "<masked-token>" in sanitized


# ── 7. ChaosFaultRunner Argument Injection Guards ────────────────────────────


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


# ── 8. Structural Diff Ref Injection Guards ──────────────────────────────────


def test_structural_diff_rejects_flag_injection_refs() -> None:
    """Verify that get_structural_diff rejects branch/base with leading hyphens."""
    res = get_structural_diff(
        path_a="src/devops_cli/main.py",
        branch="--output=/tmp/evil",
        base="main",
    )
    assert "Error:" in res or res == ""


# ── 9. LangChain Tool Kwargs Percent-Encoded Traversal Guards ─────────────────


def test_validate_langchain_kwargs_detects_percent_encoded_traversal() -> None:
    """Verify that _validate_langchain_kwargs catches percent-encoded traversal."""
    err = _validate_langchain_kwargs({"file_path": "%2e%2e/etc/passwd"})
    assert err is not None
    assert "traversal" in err.lower()
