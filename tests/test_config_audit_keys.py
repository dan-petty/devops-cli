"""Tests for OS Keyring secret health auditor and zero-plaintext compliance scanner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.config import app

runner = CliRunner()


def test_config_audit_keys_dry_run() -> None:
    """Verify dry-run execution of config audit-keys command."""
    result = runner.invoke(app, ["audit-keys", "--dry-run"])
    assert result.exit_code == 0
    assert "COMPLIANT_DRY_RUN" in result.output or "audit_keyring_and_secrets" in result.output


def test_config_audit_keys_json_output() -> None:
    """Verify structured JSON output from config audit-keys."""
    result = runner.invoke(app, ["audit-keys", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "keyring_backend" in data
    assert "keys" in data
    assert "is_compliant" in data
    assert len(data["keys"]) == 7

    keys = {k["key"] for k in data["keys"]}
    assert "github.token" in keys
    assert "grafana.token" in keys
    assert "grafana.password" in keys
    assert "argocd.token" in keys
    assert "argocd.password" in keys
    assert "ai.api_key" in keys
    assert "qdrant.api_key" in keys


def test_config_audit_keys_table_rendering() -> None:
    """Verify table rendering of key audit states."""
    result = runner.invoke(app, ["audit-keys"])
    assert result.exit_code == 0
    assert "Keyring & Secret Health Audit" in result.output
    assert "github.token" in result.output
    assert "Zero-Plaintext Check" in result.output


def test_config_audit_keys_plaintext_leak_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that a plaintext secret in config file triggers leak detection and non-compliant status."""
    leaked_config = tmp_path / "config.yaml"
    leaked_config.write_text("github:\n  token: ghp_leakedplaintexttoken123456\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(leaked_config))

    result = runner.invoke(app, ["audit-keys", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["is_compliant"] is False
    assert any("github.token" in leak for leak in data["plaintext_leaks"])
