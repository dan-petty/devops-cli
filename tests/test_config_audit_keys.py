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
    assert (
        "keyring_backend" in data,
        "keys" in data,
        "is_compliant" in data,
        len(data["keys"]),
    ) == (True, True, True, 12)

    keys = {k["key"] for k in data["keys"]}
    assert (
        not [key for key in keys if key.partition(".")[0] == "github"],
        "grafana.token" in keys,
        "grafana.password" in keys,
        "argocd.token" in keys,
        "argocd.password" in keys,
        "ai.api_key" in keys,
        "qdrant.api_key" in keys,
        "valkey.password" in keys,
        "runs.index_password" in keys,
        "telemetry.logfire_token" in keys,
        "cloudflare.api_token" in keys,
        "service.webhook_secrets" in keys,
    ) == (True, True, True, True, True, True, True, True, True, True, True, True)


def test_config_audit_keys_table_rendering() -> None:
    """Verify table rendering of key audit states."""
    result = runner.invoke(app, ["audit-keys"])
    assert result.exit_code == 0
    assert "Keyring & Secret Health Audit" in result.output
    assert "grafana.token" in result.output
    assert "Zero-Plaintext Check" in result.output


def test_config_audit_keys_plaintext_leak_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that a plaintext secret in config file triggers leak detection and non-compliant status."""
    leaked_config = tmp_path / "config.yaml"
    leaked_config.write_text("grafana:\n  token: FAKE-leaked-plaintext-token\n", encoding="utf-8")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(leaked_config))

    result = runner.invoke(app, ["audit-keys", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["is_compliant"] is False
    assert any("grafana.token" in leak for leak in data["plaintext_leaks"])


def test_config_audit_keys_flags_a_secret_key_that_is_no_longer_an_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plaintext GitHub token left under `github:` is still a leak, though no option reads it."""
    stale_config = tmp_path / "config.yaml"
    stale_config.write_text(
        "github:\n  token: FAKE-stale-token\n  default_org: octo\n", encoding="utf-8"
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(stale_config))

    data = json.loads(runner.invoke(app, ["audit-keys", "--json"]).output)
    leaked = [leak.partition(":")[2].split(".") for leak in data["plaintext_leaks"]]
    assert (data["is_compliant"], leaked) == (False, [["github", "token"]])
